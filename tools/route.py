"""Planes, autorouting and zone fill for the RT1176 MicroMod card.

  python3 tools/route.py [--passes N]      (after tools/pcbgen.py)

1. Adds the plane zones: In1 GND; In4 +3V3 with a DCDC_DIG island (BGA core balls -> right-band bulk caps).
2. Marks In1/In4 as power layers, so the router keeps signals on F.Cu, In2.Cu, In3.Cu and B.Cu.
3. Exports Specctra DSN, adds a power net class (wider tracks), runs Freerouting (tools/bin/freerouting-1.4.4.jar,
   built by tools/build_freerouting.sh) and imports the session back.
4. Refills the zones and saves rt1176-micromod-som.kicad_pcb (the unrouted board is kept as *-placed.kicad_pcb)."""
import os, re, shutil, subprocess, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from pcbgen import P, MM, WIDTH, OUT, VIA_D, VIA_DRILL
JAR = os.path.join(HERE, 'bin', 'freerouting-1.4.4.jar')
WORK = os.path.join(ROOT, 'build', 'route'); os.makedirs(WORK, exist_ok=True)

POWER_CLASS = {'GND': 0.2, '+3V3': 0.2, 'DCDC_DIG': 0.25, 'DCDC_ANA': 0.2, 'VDD_SNVS_ANA': 0.15, 'VDD_SNVS_DIG': 0.15,
               'DCDC_LP': 0.3, 'DCDC_LN': 0.3, 'VDDA_ADC_3P3': 0.15, 'ADC_VREFH': 0.15, 'VDD_MIPI_1P0': 0.15,
               'VDD_MIPI_1P8': 0.15, 'VDD_SNVS_IN': 0.15}

def zone(b, layer, netname, pts, prio=0, clear=0.15):
    z = pcbnew.ZONE(b); z.SetLayer(b.GetLayerID(layer)); z.SetNet(b.FindNet(netname))
    o = z.Outline(); o.NewOutline()
    for x, y in pts: o.Append(P(x, y))
    z.SetAssignedPriority(prio); z.SetLocalClearance(MM(clear)); z.SetMinThickness(MM(0.15))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL); z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    b.Add(z); return z

def add_planes(b):
    if len(b.Zones()):                          # already there (--continue): keep them, just set the layer types
        set_layer_types(b); return
    W = WIDTH
    full = [(-0.5, 1.2), (W + 0.5, 1.2), (W + 0.5, 22.5), (-0.5, 22.5)]   # clipped to the outline; stays off the finger bevel
    zone(b, 'In1.Cu', 'GND', full)
    zone(b, 'In4.Cu', '+3V3', full)
    island = [(9.1, 9.7), (13.9, 9.7), (13.9, 11.3), (19.3, 11.3), (19.3, 4.6), (W + 0.5, 4.6), (W + 0.5, 15.4), (19.3, 15.4),
              (19.3, 13.0), (13.9, 13.0), (13.9, 13.7), (9.1, 13.7)]
    zone(b, 'In4.Cu', 'DCDC_DIG', island, prio=1)
    set_layer_types(b)

def set_layer_types(b):
    for l in ('In1.Cu', 'In4.Cu'): b.SetLayerType(b.GetLayerID(l), pcbnew.LT_POWER)
    for l in ('F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu'): b.SetLayerType(b.GetLayerID(l), pcbnew.LT_SIGNAL)

def fill(b):
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())

def patch_dsn(path, b):
    """shrink the routing boundary by the copper-to-edge clearance (Freerouting ignores it) and add the power classes"""
    s = open(path).read()
    ps = pcbnew.SHAPE_POLY_SET(); assert b.GetBoardPolygonOutlines(ps)
    ps.Deflate(MM(0.3), 16, pcbnew.SHAPE_POLY_SET.ROUND_ALL_CORNERS)
    o = ps.Outline(0); pts = [o.CPoint(i) for i in range(o.PointCount())] + [o.CPoint(0)]
    path_ = ' '.join(f'{p.x / 1000:.1f} {-p.y / 1000:.1f}' for p in pts)
    i = s.index('(boundary'); j = s.index(')', s.index('(path', i)) + 1
    s = s[:i] + f'(boundary\n      (path pcb 0 {path_})' + s[j:]
    m = re.search(r'\(class kicad_default "" (.*?)\(circuit', s, re.S)
    assert m, 'no default class in DSN'
    nets = m.group(1).split()
    keep = [n for n in nets if n.strip('"') not in POWER_CLASS]
    s = s[:m.start(1)] + ' '.join(keep) + '\n      ' + s[m.end(1):]
    cls = []
    for n, w in POWER_CLASS.items():
        q = f'"{n}"' if not re.fullmatch(r'[A-Za-z0-9_]+', n) else n
        if q in nets or f'"{n}"' in nets or n in nets:
            cls.append(f'    (class pwr_{len(cls)} {q}\n      (circuit\n        (use_via Via[0-5]_{VIA_D * 1000:.0f}:{VIA_DRILL * 1000:.0f}_um)\n      )\n'
                       f'      (rule\n        (width {w * 1000:.0f})\n        (clearance 100)\n      )\n    )\n')
    i = s.index('(class kicad_default')
    s = s[:i] + ''.join(cls) + '    ' + s[i:]
    open(path, 'w').write(s)
    return len(cls)

def sexp(text):
    toks = re.findall(r'\(|\)|"[^"]*"|[^\s()]+', text); st = [[]]
    for t in toks:
        if t == '(': st.append([])
        elif t == ')': x = st.pop(); st[-1].append(x)
        else: st[-1].append(t.strip('"'))
    return st[0][0]

def import_ses(b, path):
    """KiCad 7's ImportSpecctraSES only works inside the editor, so read the session here:
    wires become tracks and vias become VIA_D/VIA_DRILL through vias (Specctra y is KiCad -y)."""
    ses = sexp(open(path).read())
    routes = next(x for x in ses if isinstance(x, list) and x[0] == 'routes')
    res = next(x for x in routes if isinstance(x, list) and x[0] == 'resolution')
    scale = {'um': 1e3, 'mm': 1e6, 'mil': 25400}[res[1]] / float(res[2])         # nm per unit
    no = next(x for x in routes if isinstance(x, list) and x[0] == 'network_out')
    layers = {b.GetLayerName(l): l for l in range(pcbnew.PCB_LAYER_ID_COUNT)}
    for t in list(b.GetTracks()): b.Remove(t)            # the session carries the whole routing, fan-out included
    nt = nv = 0
    for n in no[1:]:
        net = b.FindNet(n[1]); assert net, n[1]
        for item in n[2:]:
            if item[0] == 'wire':
                path_ = next(x for x in item if isinstance(x, list) and x[0] == 'path')
                lay, w = layers[path_[1]], int(float(path_[2]) * scale); c = [float(v) for v in path_[3:]]
                pts = [pcbnew.VECTOR2I(int(c[i] * scale), int(-c[i + 1] * scale)) for i in range(0, len(c), 2)]
                for a, e in zip(pts, pts[1:]):
                    t = pcbnew.PCB_TRACK(b); t.SetStart(a); t.SetEnd(e); t.SetWidth(w); t.SetLayer(lay); t.SetNet(net); b.Add(t); nt += 1
            elif item[0] == 'via':
                v = pcbnew.PCB_VIA(b); v.SetPosition(pcbnew.VECTOR2I(int(float(item[2]) * scale), int(-float(item[3]) * scale)))
                v.SetDrill(MM(VIA_DRILL)); v.SetWidth(MM(VIA_D)); v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
                v.SetNet(net); b.Add(v); nv += 1
    return f'{nt} track segments, {nv} vias'

def main():
    passes = int(sys.argv[sys.argv.index('--passes') + 1]) if '--passes' in sys.argv else 30
    placed = OUT.replace('.kicad_pcb', '-placed.kicad_pcb')
    assert os.path.exists(placed), 'run tools/pcbgen.py first'
    src = OUT if '--continue' in sys.argv else placed          # --continue: start from the last routed board
    b = pcbnew.LoadBoard(src)
    b.GetDesignSettings().m_HoleClearance = MM(0.17)
    add_planes(b); fill(b)
    dsn = os.path.join(WORK, 'card.dsn'); ses = os.path.join(WORK, 'card.ses')
    assert pcbnew.ExportSpecctraDSN(b, dsn), 'DSN export failed'
    print('power classes', patch_dsn(dsn, b))
    if os.path.exists(ses): os.remove(ses)
    cmd = ['xvfb-run', '-a', 'java', '-jar', JAR, '-de', dsn, '-do', ses, '-mp', str(passes)]
    print(' '.join(cmd)); sys.stdout.flush()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
    open(os.path.join(WORK, 'freerouting.log'), 'w').write(r.stdout + r.stderr)
    assert os.path.exists(ses), 'Freerouting wrote no session; see build/route/freerouting.log'
    print('imported', import_ses(b, ses))
    fill(b)
    pcbnew.SaveBoard(OUT, b)
    print('routed board saved', OUT)

if __name__ == '__main__':
    main()
