# Writes Ghidra's decompiled C for every function to text files. Run headless
# as a post-script (see README.md, "Ghidra"); the output folder is the script
# argument. Output is derived from game code: it goes in decomp/, never in git.
# @category BeatDown
# @runtime PyGhidra
import os
from ghidra.app.decompiler import DecompInterface, DecompileOptions
from ghidra.util.task import ConsoleTaskMonitor

args = getScriptArgs()
out = args[0] if args else os.path.join(os.getcwd(), 'decomp')
funcs_dir = os.path.join(out, 'funcs')
os.makedirs(funcs_dir, exist_ok=True)

opts = DecompileOptions()
opts.grabFromProgram(currentProgram)
ifc = DecompInterface()
ifc.setOptions(opts)
ifc.toggleCCode(True)
ifc.toggleSyntaxTree(False)
ifc.openProgram(currentProgram)
mon = ConsoleTaskMonitor()

fm = currentProgram.getFunctionManager()
index = ['address\tname\tsize\tfile\tstatus']
done = failed = 0
with open(os.path.join(out, 'all.c'), 'w', encoding='utf-8', newline='\n') as allc:
    for f in fm.getFunctions(True):
        addr = '%08X' % f.getEntryPoint().getOffset()
        name = f.getName()
        size = f.getBody().getNumAddresses()
        res = ifc.decompileFunction(f, 120, mon)
        if res is not None and res.decompileCompleted():
            # Ghidra emits CRLF on Windows; keep plain LF
            code = res.getDecompiledFunction().getC().replace('\r\n', '\n')
            status = 'ok'
            done += 1
        else:
            msg = res.getErrorMessage() if res is not None else 'no result'
            code = '/* decompile failed: %s */\n' % msg.strip()
            status = 'failed'
            failed += 1
        fn = '%s_%s.c' % (addr, ''.join(c if c.isalnum() or c in '_.' else '_' for c in name)[:80])
        header = '// %s @ 0x%s, %d bytes\n' % (name, addr, size)
        with open(os.path.join(funcs_dir, fn), 'w', encoding='utf-8', newline='\n') as fh:
            fh.write(header + code)
        allc.write(header + code + '\n')
        index.append('%s\t%s\t%d\tfuncs/%s\t%s' % (addr, name, size, fn, status))

with open(os.path.join(out, 'index.tsv'), 'w', encoding='utf-8', newline='\n') as fh:
    fh.write('\n'.join(index) + '\n')
ifc.dispose()
print('Exported %d functions (%d failed) to %s' % (done, failed, out))
