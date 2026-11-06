"""Run KiCad's DRC on the board through the pcbnew API (KiCad 7's CLI has no DRC) and summarise it.
  python3 tools/drc.py [board] [--show type,type]"""
import collections, os, re, sys, tempfile
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
av = sys.argv[1:]
if '--show' in av: i = av.index('--show'); av = av[:i] + av[i + 2:]
args = av
brd = args[0] if args else os.path.join(ROOT, 'rt1176-micromod-som.kicad_pcb')
show = set(sys.argv[sys.argv.index('--show') + 1].split(',')) if '--show' in sys.argv else set()
b = pcbnew.LoadBoard(brd)
rpt = os.path.join(tempfile.mkdtemp(), 'drc.txt')
pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
txt = open(rpt).read()
blocks = re.split(r'\n(?=\[)', txt)
cnt = collections.Counter()
for blk in blocks:
    m = re.match(r'\[(\w+)\]', blk)
    if not m: continue
    cnt[m.group(1)] += 1
    if m.group(1) in show: print(blk.strip())
for k, v in sorted(cnt.items()): print(f'{v:5d} {k}')
