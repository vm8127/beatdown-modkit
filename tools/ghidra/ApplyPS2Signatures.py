# Names the Sony PS2 SDK library functions (libkernl, libc, libgraph, libdma,
# libpad, libcdvd, libmc, libmpeg, libm, libgcc, ...) by signature, so the
# pseudocode says sceCdRead or memcpy instead of FUN_0011xxxx. Run headless as
# a post-script before ExportDecompiled.py (see README.md, "Ghidra").
#
# The signature database is downloaded once (12 MB, see ps2sigdb.py) into
# ghidra/sigdb/, or into the folder given as the script argument. Names we
# gave ourselves (symbols/symbols.tsv, imported by ImportBeatdownSymbols.py)
# always win over signature names. What was applied is written to
# ghidra/ps2_signatures.tsv.
# @category BeatDown
# @runtime PyGhidra
import os
import struct
import sys

from ghidra.app.cmd.function import CreateFunctionCmd
from ghidra.program.model.symbol import SourceType

sys.path.insert(0, getSourceFile().getParentFile().getAbsolutePath())
import ps2sigdb  # noqa: E402

args = getScriptArgs()
cache = args[0] if args else os.path.join(os.getcwd(), 'ghidra', 'sigdb')
db_path = os.path.join(cache, ps2sigdb.DB_FILE)
if not os.path.exists(db_path):
    try:
        ps2sigdb.download(cache)
    except Exception as e:
        print('ApplyPS2Signatures: could not download the signature database (%s).' % e)
        print('Download it by hand from\n  %s\ninto %s and run again.' % (ps2sigdb.DB_URL, cache))
        raise
print('Loading PS2 SDK signatures from ' + db_path)
db = ps2sigdb.load(db_path)

prog = currentProgram
space = prog.getAddressFactory().getDefaultAddressSpace()
fm = prog.getFunctionManager()


def addr(a):
    return space.getAddress(a)


def read_block(block):
    n = int(block.getSize())
    import jpype
    buf = jpype.JArray(jpype.JByte)(n)
    block.getBytes(block.getStart(), buf)
    try:
        return memoryview(buf).tobytes()
    except TypeError:
        return bytes(b & 0xFF for b in buf)


segs = []
for block in prog.getMemory().getBlocks():
    if block.isExecute() and block.isInitialized():
        segs.append((int(block.getStart().getOffset()), read_block(block)))
if not segs:
    # Some loaders leave the execute flag off; fall back to every loaded block
    for block in prog.getMemory().getBlocks():
        if block.isInitialized() and block.isLoaded():
            segs.append((int(block.getStart().getOffset()), read_block(block)))


def code_at(a):
    for base, code in segs:
        if base <= a < base + len(code) - 3:
            return struct.unpack_from('<I', code, a - base)[0]
    return None


found = {}
sdk = None
for base, code in segs:
    sdk = sdk or ps2sigdb.sdk_version(code)
    found.update(db.scan(code, base))

known = {}
for f in fm.getFunctions(True):
    if f.getSymbol().getSource() != SourceType.DEFAULT:
        known[int(f.getEntryPoint().getOffset())] = f.getName()

names, ambiguous = ps2sigdb.resolve(found, sdk, code_at, known)

log = ['address\tname\tlibrary\tsize\tmatch\tresult']
renamed = created = kept = skipped = 0
for a, name, lib, size, strength in names:
    ea = addr(a)
    f = fm.getFunctionAt(ea)
    result = 'named'
    if f is None:
        if strength != 'strong':
            log.append('%08X\t%s\t%s\t%d\t%s\tskipped (not a function start)' % (a, name, lib, size, strength))
            skipped += 1
            continue
        # A strong match inside another function: Ghidra merged two
        # functions (the second one is only reached by fall-through or a
        # jump table). Split it out.
        outer = fm.getFunctionContaining(ea)
        if getInstructionAt(ea) is None:
            disassemble(ea)
        CreateFunctionCmd(ea).applyTo(prog, monitor)
        f = fm.getFunctionAt(ea)
        if f is None:
            log.append('%08X\t%s\t%s\t%d\t%s\tskipped (could not create function)' % (a, name, lib, size, strength))
            skipped += 1
            continue
        if outer is not None:
            CreateFunctionCmd.fixupFunctionBody(prog, outer, monitor)
        created += 1
        result = 'created'
    src = f.getSymbol().getSource()
    if src in (SourceType.USER_DEFINED, SourceType.IMPORTED) and f.getName() != name:
        log.append('%08X\t%s\t%s\t%d\t%s\tkept our name %s' % (a, name, lib, size, strength, f.getName()))
        kept += 1
        continue
    if f.getName() != name:
        try:
            f.setName(name, SourceType.ANALYSIS)
        except Exception:
            f.setName('%s_%08X' % (name, a), SourceType.ANALYSIS)
        renamed += 1
    if not f.getComment():
        f.setComment('PS2 SDK %s (signature match)' % lib)
    log.append('%08X\t%s\t%s\t%d\t%s\t%s' % (a, name, lib, size, strength, result))

for a, cands in ambiguous:
    log.append('%08X\t\t\t\tambiguous\t%s' % (a, ', '.join(cands)))

# C library prototypes (memcpy, strlen, sprintf, ...) from Ghidra's own
# generic_clib archive, only on the functions named above
try:
    from java.util import ArrayList
    from ghidra.framework import Application
    from ghidra.program.model.data import FileDataTypeManager
    from ghidra.program.model.address import AddressSet
    from ghidra.app.cmd.function import ApplyFunctionDataTypesCmd
    gdt = Application.findDataFileInAnyModule('typeinfo/generic/generic_clib.gdt')
    if gdt is not None:
        dtm = FileDataTypeManager.openFileArchive(gdt, False)
        try:
            aset = AddressSet()
            for a, name, lib, size, strength in names:
                aset.add(addr(a))
            managers = ArrayList()
            managers.add(dtm)
            ApplyFunctionDataTypesCmd(managers, aset, SourceType.ANALYSIS, False, False).applyTo(prog, monitor)
            print('Applied C library prototypes from ' + gdt.getName())
        finally:
            dtm.close()
except Exception as e:
    print('Skipped C library prototypes: %s' % e)

# Let auto-analysis follow up on the split functions and new names
analyzeChanges(prog)

out = os.path.join(os.path.dirname(os.path.abspath(cache)), 'ps2_signatures.tsv')
with open(out, 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(log) + '\n')
print('PS2 SDK %s signatures: %d named (%d new functions split out), %d kept our own name, '
      '%d skipped, %d ambiguous left alone. Log: %s' % (
          sdk, renamed, created, kept, skipped, len(ambiguous), out))
