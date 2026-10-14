# Applies symbols/inferred_types.tsv (written by `codemap.py infer-types` from the previous decomp/) to
# function parameters: for example a parameter that is only used at offsets only a Fighter has becomes
# Fighter *. Run headless as a post-script before ExportDecompiled.py (README.md, "Ghidra").
# @category BeatDown
# @runtime PyGhidra
import os
from ghidra.app.decompiler import DecompInterface
from ghidra.program.model.data import CategoryPath, PointerDataType
from ghidra.program.model.pcode import HighFunctionDBUtil
from ghidra.program.model.symbol import SourceType
from ghidra.util.task import ConsoleTaskMonitor

path = None
for d in getScriptArgs() or []:
    path = d
if path is None:
    for root in [os.getcwd()]:
        p = os.path.join(root, 'symbols', 'inferred_types.tsv')
        if os.path.exists(p):
            path = p
if path is None or not os.path.exists(path):
    print('ApplyInferredTypes: no symbols/inferred_types.tsv, nothing to do')
else:
    dtm = currentProgram.getDataTypeManager()
    ifc = DecompInterface()
    ifc.openProgram(currentProgram)
    mon = ConsoleTaskMonitor()
    fm = currentProgram.getFunctionManager()
    done = skipped = 0
    for line in open(path, encoding='utf-8'):
        if line.startswith('#') or not line.strip():
            continue
        addr, name, idx, typ = line.rstrip('\n').split('\t')[:4]
        f = fm.getFunctionAt(toAddr(int(addr, 16)))
        base = dtm.getDataType(CategoryPath('/BeatDown'), typ.rstrip(' *'))
        if f is None or base is None or f.getSignatureSource() == SourceType.USER_DEFINED:
            skipped += 1
            continue
        res = ifc.decompileFunction(f, 60, mon)
        if res is None or not res.decompileCompleted():
            skipped += 1
            continue
        HighFunctionDBUtil.commitParamsToDatabase(res.getHighFunction(), True,
                                                  HighFunctionDBUtil.ReturnCommitOption.NO_COMMIT,
                                                  SourceType.ANALYSIS)
        i = int(idx)
        if i >= f.getParameterCount():
            skipped += 1
            continue
        f.getParameter(i).setDataType(PointerDataType(base, 4, dtm), SourceType.ANALYSIS)
        done += 1
    ifc.dispose()
    print('ApplyInferredTypes: typed %d parameters (%d skipped) from %s' % (done, skipped, path))
