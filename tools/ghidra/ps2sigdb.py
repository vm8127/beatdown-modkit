# Sony PS2 SDK (libsce) function signatures: finds library functions in an EE
# executable by hashing their code with relocated fields masked out.
#
# The signature database is the sce-symbol-scanner "symboldb" (5,300+ names
# from libkernl, libc, libgraph, libdma, libpad, libcdvd, libmc, libmpeg, libm,
# libgcc, ...), built from PS2 games that kept their debug symbols. It ships
# embedded in PS2Recomp (GPL-3.0); we download that one header and read the
# JSON out of it. The data stays in a local cache and is never committed.
#
# Plain Python 3, no Ghidra imports: ApplyPS2Signatures.py uses it inside
# Ghidra, and `python tools/ghidra/ps2sigdb.py ISO/SLUS_211.50` runs the same
# scan without Ghidra (prints what would be named).
import hashlib
import json
import os
import re
import struct
import sys
import urllib.request

DB_URL = ('https://raw.githubusercontent.com/ran-j/PS2Recomp/'
          '2c5fbb9389e11dd95693385969490c9e8e6f57b4/'
          'ps2xAnalyzer/include/ps2recomp/sce_symbol_database_data.h')
DB_FILE = 'sce_symbol_database_data.h'
DB_SHA256 = '0fdd1168a815c8af2529cae9076ae813a1304c5c3a41e48d88d38e21e7b5833d'

# Bits of the instruction word that stay fixed under each relocation type
MASKS = {
    'NONE': 0xFFFFFFFF, 'MIPS_26': 0xFC000000, 'MIPS_LO16': 0xFFFF0000,
    'MIPS_HI16': 0xFFFF0000, 'MIPS_GPREL16': 0xFFFF0000,
    'MIPS_LITERAL': 0xFFFF0000, 'MIPS_32': 0,
}
ALIASES = {'LO16': 'MIPS_LO16', 'HI16': 'MIPS_HI16', 'MIPS26': 'MIPS_26',
           'MIPS32': 'MIPS_32', 'MIPSLO16': 'MIPS_LO16', 'MIPSHI16': 'MIPS_HI16',
           'MIPSGPREL16': 'MIPS_GPREL16', 'MIPSLITERAL': 'MIPS_LITERAL'}
LOST_BITS = {0xFFFFFFFF: 0, 0xFC000000: 26, 0xFFFF0000: 16, 0: 32}

# A hash over fewer fixed bits than this is too generic to trust on its own
# (same threshold as PS2Recomp's analyzer)
STRONG_BITS = 256
# Weak matches still count when they are unambiguous, at least this big and
# from a library that already has strong matches in the same program
WEAK_MIN_SIZE = 20


def mask_of(rel_type):
    t = (rel_type or 'none').upper()
    return MASKS.get(ALIASES.get(t, t), 0xFFFFFFFF)


def download(cache_dir, log=print):
    """Return the path of the cached database header, downloading it once."""
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, DB_FILE)
    if not os.path.exists(path):
        log('Downloading the PS2 SDK signature database (12 MB) from\n  ' + DB_URL)
        tmp = path + '.part'
        urllib.request.urlretrieve(DB_URL, tmp)
        got = check_sha256(tmp)
        if got != DB_SHA256:
            os.remove(tmp)
            raise RuntimeError('signature database download is corrupt (sha256 %s)' % got)
        os.replace(tmp, path)
    return path


def check_sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    """Load symbols.json + tree.json from the PS2Recomp header, or from a
    folder that has both files (an sce-symbol-scanner checkout)."""
    if os.path.isdir(path):
        with open(os.path.join(path, 'symbols.json'), encoding='utf-8') as fh:
            symbols = json.load(fh)
        with open(os.path.join(path, 'tree.json'), encoding='utf-8') as fh:
            tree = json.load(fh)
        return SigDB(symbols, tree)
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    parts = {}
    for name in ('kSymbolsJsonChunks', 'kTreeJsonChunks'):
        i = text.index(name)
        j = text.index('};', i)
        parts[name] = ''.join(re.findall(r'R"PS2SDB\((.*?)\)PS2SDB"', text[i:j], re.S))
    return SigDB(json.loads(parts['kSymbolsJsonChunks']), json.loads(parts['kTreeJsonChunks']))


class Sig(object):
    __slots__ = ('library', 'name', 'hash', 'size', 'relocs', 'static_bits', 'sdk', 'calls')

    def __init__(self, library, name, hsh, rec):
        self.library = library
        self.name = name
        self.hash = hsh
        self.size = int(rec.get('size', 0))
        self.relocs = []
        self.calls = []  # (offset, callee name) of each jal/j to a named symbol
        lost = 0
        for off, r in rec.get('relocations', {}).items():
            m = mask_of(r.get('type'))
            self.relocs.append((int(off, 0), m))
            lost += LOST_BITS[m]
            if m == 0xFC000000 and r.get('symbol') and not r['symbol'].startswith('<'):
                self.calls.append((int(off, 0), r['symbol']))
        self.static_bits = max(0, self.size * 8 - lost)
        self.sdk = rec.get('sdk', [])

    def matches(self, code, off):
        b = bytearray(code[off:off + self.size])
        for ro, m in self.relocs:
            if ro + 4 <= len(b):
                v = struct.unpack_from('<I', b, ro)[0] & m
                struct.pack_into('<I', b, ro, v)
        return hashlib.sha1(b).hexdigest() == self.hash


class SigDB(object):
    def __init__(self, symbols, tree):
        self.sigs = {}
        for lib, names in symbols.items():
            for name, hashes in names.items():
                for hsh, variants in hashes.items():
                    for var, rec in variants.items():
                        if str(rec.get('type', '')).upper() not in ('FUNCTION', 'FUNC'):
                            continue
                        if not rec.get('size'):
                            continue
                        self.sigs[(lib, name, hsh, int(var, 16))] = Sig(lib, name, hsh, rec)
        # The prefix tree's root tests the word at offset 0 against ~900
        # values; index those by (mask, value) so each address costs a few
        # dict lookups instead of a 900-way loop.
        self.root = {}
        for edge in tree.get('next', []):
            m = mask_of(edge['match'].get('relocation', {}).get('type'))
            v = edge['match'].get('value', 0) & m
            self.root.setdefault(m, {}).setdefault(v, []).append(edge['child'])
        assert tree.get('offset', 0) == 0

    def _walk(self, node, code, off, out):
        o = off + node.get('offset', 0)
        if o + 4 > len(code):
            return
        w = struct.unpack_from('<I', code, o)[0]
        for edge in node.get('next', []):
            m = mask_of(edge['match'].get('relocation', {}).get('type'))
            if (w & m) == (edge['match'].get('value', 0) & m):
                self._collect(edge['child'], code, off, out)

    def _collect(self, child, code, off, out):
        for s in child.get('symbols', []):
            out.append((s.get('library', ''), s.get('name', ''), s.get('hash', ''), s.get('variant', 0)))
        if child.get('next'):
            self._walk(child, code, off, out)

    def scan(self, code, base):
        """Every hash match in `code` (bytes loaded at address `base`):
        {address: [Sig, ...]}"""
        found = {}
        n = len(code) - 4
        roots = list(self.root.items())
        unpack = struct.unpack_from
        for off in range(0, n, 4):
            w = unpack('<I', code, off)[0]
            keys = None
            for m, table in roots:
                kids = table.get(w & m)
                if kids:
                    if keys is None:
                        keys = []
                    for child in kids:
                        self._collect(child, code, off, keys)
            if not keys:
                continue
            for k in set(keys):
                sig = self.sigs.get(k)
                if sig is None or off + sig.size > len(code):
                    continue
                if sig.matches(code, off):
                    found.setdefault(base + off, []).append(sig)
        return found


def sdk_version(code):
    """SDK release the program was linked against, from libsce's own
    'PsIIlibkernl3000'-style tags, as '3.0' (major.minor); None if absent."""
    m = re.search(rb'PsIIlib\w{1,6}\s*(\d)(\d)(\d)\d', code)
    return '%s.%s' % (m.group(1).decode(), m.group(2).decode()) if m else None


def _jump_target(code_at, addr, off):
    w = code_at(addr + off)
    if w is None:
        return None
    return ((addr + off + 4) & 0xF0000000) | ((w & 0x03FFFFFF) << 2)


def resolve(found, sdk=None, code_at=None, known=None):
    """Pick one name per address. Returns (named, ambiguous): named is a list
    of (address, name, library, size, strength), ambiguous a list of
    (address, [candidate names]) that were left alone.

    code_at(address) -> instruction word (or None) lets candidates that
    share the same code be told apart by what they call (DisableIntc calls
    _DisableIntc, EnableIntc calls _EnableIntc). known is {address: name}
    of functions the program already names (syscall stubs and the like)."""
    def narrow(sigs):
        # Prefer variants seen in the program's own SDK release
        if sdk:
            same = [s for s in sigs if any(v.startswith(sdk) for v in s.sdk)]
            if same:
                sigs = same
        return sigs

    def names_of(sigs):
        return sorted(set(s.name for s in sigs))

    def best(sigs):
        b = max(sigs, key=lambda s: (s.size, s.static_bits))
        libs = sorted(set(s.library for s in sigs if s.name == b.name))
        return b, '/'.join(libs)

    pending = {}
    for addr, sigs in found.items():
        strong = [s for s in sigs if s.static_bits >= STRONG_BITS]
        if strong:
            pending[addr] = (narrow(strong), 'strong')
        else:
            sigs = narrow(sigs)
            if max(s.size for s in sigs) >= WEAK_MIN_SIZE:
                pending[addr] = (sigs, 'weak')

    named = {}
    for _ in range(3):
        progress = False
        name_at = dict(known or {})
        name_at.update((a, n[0]) for a, n in named.items())
        for addr in sorted(pending):
            if addr in named:
                continue
            sigs, strength = pending[addr]
            if len(names_of(sigs)) > 1 and code_at is not None and name_at:
                scored = []
                for s in sigs:
                    score = 0
                    for off, callee in s.calls:
                        t = name_at.get(_jump_target(code_at, addr, off))
                        if t is None:
                            continue
                        score += 1 if t == callee else -1000
                    scored.append((score, s))
                top = max(sc for sc, _ in scored)
                if top > 0:
                    sigs = [s for sc, s in scored if sc == top]
            if len(names_of(sigs)) > 1 and len(set(x.library for x in sigs)) > 1:
                # Same code under two libraries' names (libkernl's Timer*
                # vs libtimer's sceTimer*): take the library this program
                # already uses most
                count = {}
                for n in named.values():
                    if n[3] == 'strong':
                        for lib in n[1].split('/'):
                            count[lib] = count.get(lib, 0) + 1
                top = max(count.get(x.library, 0) for x in sigs)
                pref = [x for x in sigs if count.get(x.library, 0) == top]
                if top > 0 and len(set(x.library for x in pref)) == 1:
                    sigs = pref
            if len(names_of(sigs)) == 1:
                b, libs = best(sigs)
                named[addr] = (b.name, libs, b.size, strength)
                progress = True
        if not progress:
            break

    libs_seen = set()
    for n in named.values():
        if n[3] == 'strong':
            libs_seen.update(n[1].split('/'))
    out = [(a,) + n for a, n in sorted(named.items())
           if n[3] == 'strong' or set(n[1].split('/')) & libs_seen]
    # A name found at several addresses: identical static copies are fine
    # when every copy is a strong match; otherwise drop the weak copies
    by_name = {}
    for c in out:
        by_name.setdefault(c[1], []).append(c)
    keep, ambiguous = [], []
    for c in out:
        same = by_name[c[1]]
        if len(same) == 1 or c[4] == 'strong':
            keep.append(c)
        else:
            ambiguous.append((c[0], ['%s (also at %s)' % (c[1], ','.join(
                '%08X' % x[0] for x in same if x is not c))]))
    for addr, (sigs, _) in pending.items():
        if addr not in named:
            ambiguous.append((addr, names_of(sigs)))
    ambiguous.sort()
    return keep, ambiguous


def elf_code(path):
    """(base address, bytes) of each executable PT_LOAD segment of a MIPS ELF."""
    with open(path, 'rb') as fh:
        data = fh.read()
    if data[:4] != b'\x7fELF':
        raise ValueError('not an ELF file: ' + path)
    phoff, = struct.unpack_from('<I', data, 0x1C)
    phentsize, phnum = struct.unpack_from('<HH', data, 0x2A)
    segs = []
    for i in range(phnum):
        p_type, p_off, p_vaddr, _, p_filesz, _, p_flags, _ = struct.unpack_from(
            '<8I', data, phoff + i * phentsize)
        if p_type == 1 and p_filesz and (p_flags & 1):
            segs.append((p_vaddr, data[p_off:p_off + p_filesz]))
    return segs


def main(argv):
    import argparse
    ap = argparse.ArgumentParser(description='Find Sony PS2 SDK library functions in an EE ELF (no Ghidra needed).')
    ap.add_argument('elf')
    ap.add_argument('--db', help='database header or symboldb folder (default: download to ghidra/sigdb/)')
    ap.add_argument('--out', help='write address/name/library/size/strength TSV here')
    ap.add_argument('--known', help='TSV of address<TAB>name already named in the program (e.g. decomp/index.tsv)')
    ap.add_argument('--ambiguous', action='store_true', help='also list the addresses left unnamed and their candidates')
    a = ap.parse_args(argv)
    db_path = a.db or download(os.path.join('ghidra', 'sigdb'))
    db = load(db_path)
    found = {}
    sdk = None
    segs = elf_code(a.elf)
    for base, code in segs:
        sdk = sdk or sdk_version(code)
        found.update(db.scan(code, base))

    def code_at(addr):
        for base, code in segs:
            if base <= addr < base + len(code) - 3:
                return struct.unpack_from('<I', code, addr - base)[0]
        return None
    known = {}
    if a.known:
        with open(a.known, encoding='utf-8') as fh:
            for line in fh:
                f = line.rstrip('\n').split('\t')
                if len(f) >= 2 and re.match(r'^(0x)?[0-9A-Fa-f]{8}$', f[0]) \
                        and not f[1].startswith(('FUN_', 'thunk_FUN_')):
                    known[int(f[0], 16)] = f[1]
    names, amb = resolve(found, sdk, code_at, known)
    lines = ['%08X\t%s\t%s\t%d\t%s' % n for n in names]
    if a.out:
        with open(a.out, 'w', encoding='utf-8', newline='\n') as fh:
            fh.write('address\tname\tlibrary\tsize\tmatch\n' + '\n'.join(lines) + '\n')
    else:
        print('\n'.join(lines))
    if a.ambiguous:
        for addr, cands in amb:
            print('%08X\t%s' % (addr, ', '.join(cands)), file=sys.stderr)
    print('SDK %s: %d functions named (%d strong), %d ambiguous skipped' % (
        sdk, len(names), sum(1 for n in names if n[4] == 'strong'), len(amb)), file=sys.stderr)


if __name__ == '__main__':
    main(sys.argv[1:])
