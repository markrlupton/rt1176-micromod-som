"""Generate the RT1176 MicroMod SOM board (KiCad 7, pcbnew API).

  python3 tools/pcbgen.py            -> rt1176-micromod-som.kicad_pcb (placed + fanned out + planes, unrouted)

Card frame used below ("card mm"): SparkFun MicroMod coordinates, top view, x = 0 at the pin-75 side, x grows
toward pin 1, y = 0 at the finger edge and grows away from it. Board coordinates: X = 100 + x, Y = 122 - y.
Net data comes from tools/schgen.py (data/design_nets.json, data/u1_nets.json), so the board always matches
the schematic.
"""
import json, math, os, sys
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DATA = os.path.join(HERE, 'data')
OUT = os.path.join(ROOT, 'rt1176-micromod-som.kicad_pcb')
KFP = '/usr/share/kicad/footprints'
MM = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(MM(float(100 + x)), MM(float(122 - y)))
def card(v): return (pcbnew.ToMM(v.x) - 100, 122 - pcbnew.ToMM(v.y))

WIDTH = 22.8                       # MicroMod 22 mm + 0.8 mm on the pin-1 side
U1_C = (11.5, 12.1)                # BGA centre (card mm)
VIA_D, VIA_DRILL = 0.3, 0.15                # JLC 6-layer minimum: 0.15 mm hole, 0.075 mm ring
TRACK, CLEAR = 0.1, 0.1

# ------------------------------------------------------------------ board + rules
def new_board():
    b = pcbnew.BOARD()
    b.SetCopperLayerCount(6)
    ds = b.GetDesignSettings()
    ds.SetCopperLayerCount(6)
    ds.SetBoardThickness(MM(0.8))
    ds.m_TrackMinWidth = MM(0.09); ds.m_ViasMinSize = MM(0.25); ds.m_MinThroughDrill = MM(0.15)
    ds.m_MinClearance = MM(0.09); ds.m_HoleClearance = MM(0.2); ds.m_CopperEdgeClearance = MM(0.25)
    ds.m_ViasMinAnnularWidth = MM(0.075); ds.m_HoleToHoleMin = MM(0.25)
    nc = ds.m_NetSettings.m_DefaultNetClass
    nc.SetClearance(MM(CLEAR)); nc.SetTrackWidth(MM(TRACK)); nc.SetViaDiameter(MM(VIA_D)); nc.SetViaDrill(MM(VIA_DRILL))
    for i, name in enumerate(['F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu']):
        pass
    return b

# ------------------------------------------------------------------ outline
def seg(b, a, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_SEGMENT); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(P(*a)); s.SetEnd(P(*c)); s.SetWidth(MM(0.05)); b.Add(s)
def arc(b, a, m, c):
    s = pcbnew.PCB_SHAPE(b); s.SetShape(pcbnew.SHAPE_T_ARC); s.SetLayer(pcbnew.Edge_Cuts)
    s.SetArcGeometry(P(*a), P(*m), P(*c)); s.SetWidth(MM(0.05)); b.Add(s)
def mid_arc(a, c, centre):
    """midpoint of the minor arc from a to c around centre"""
    ang = lambda p: math.atan2(p[1] - centre[1], p[0] - centre[0])
    a1, a2 = ang(a), ang(c); d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
    r = math.dist(a, centre); t = a1 + d / 2
    return (centre[0] + r * math.cos(t), centre[1] + r * math.sin(t))

def outline(b):
    W = WIDTH
    seg(b, (1.075, 0), (13.025, 0))
    seg(b, (13.025, 0), (13.025, 2.89)); arc(b, (13.025, 2.89), (13.625, 3.49), (14.225, 2.89)); seg(b, (14.225, 2.89), (14.225, 0))
    seg(b, (14.225, 0), (20.925, 0)); seg(b, (20.925, 0), (20.925, 3.49))
    arc(b, (20.925, 3.49), mid_arc((20.925, 3.49), (21.4, 3.99), (21.4, 3.49)), (21.4, 3.99))     # fillet, r 0.5
    seg(b, (21.4, 3.99), (W - 0.6, 3.99))
    arc(b, (W - 0.6, 3.99), mid_arc((W - 0.6, 3.99), (W, 4.59), (W - 0.6, 4.59)), (W, 4.59))
    seg(b, (W, 4.59), (W, 20.99))
    arc(b, (W, 20.99), mid_arc((W, 20.99), (W - 1, 21.99), (W - 1, 20.99)), (W - 1, 21.99))
    seg(b, (W - 1, 21.99), (16.75, 21.99))
    arc(b, (16.75, 21.99), (15.0, 20.24), (13.25, 21.99))                                          # M2.5 screw half-hole
    seg(b, (13.25, 21.99), (1, 21.99))
    arc(b, (1, 21.99), mid_arc((1, 21.99), (0, 20.99), (1, 20.99)), (0, 20.99))
    seg(b, (0, 20.99), (0, 4.59))
    arc(b, (0, 4.59), mid_arc((0, 4.59), (0.6, 3.99), (0.6, 4.59)), (0.6, 3.99))
    arc(b, (0.6, 3.99), mid_arc((0.6, 3.99), (1.075, 3.49), (0.6, 3.49)), (1.075, 3.49))
    seg(b, (1.075, 3.49), (1.075, 0))

# ------------------------------------------------------------------ parts
design = json.load(open(os.path.join(DATA, 'design_nets.json')))
u1nets = json.load(open(os.path.join(DATA, 'u1_nets.json')))
fpinfo = json.load(open(os.path.join(DATA, 'design_fp.json')))      # ref -> footprint lib:name, value, fields

def load_fp(libname):
    lib, name = libname.split(':')
    path = os.path.join(ROOT, 'lib', 'rt1176-som.pretty') if lib == 'rt1176-som' else os.path.join(KFP, lib + '.pretty')
    fp = pcbnew.FootprintLoad(path, name); assert fp, libname
    fp.SetFPID(pcbnew.LIB_ID(lib, name)); return fp

# Placement (card mm, rotation deg, side). Every 0402 goes under the BGA (bottom side) in the fan-out step.
PLACE = {
    'U1': (U1_C[0], U1_C[1], -90, 'F'), 'J1': (11.0, 0.0, 0, 'F'),
    # top, left band: crystals next to their balls, DCDC inductor next to DCDC_LP/LN
    'Y1': (2.25, 6.45, 90, 'F'), 'Y2': (2.25, 10.6, 90, 'F'), 'L1': (2.15, 16.3, 90, 'F'),
    # top, top band (left of the screw keep-out): 3.3 V / DCDC_IN bulk
    'C1': (2.45, 20.55, 0, 'F'), 'C2': (5.95, 20.55, 0, 'F'), 'C7': (9.45, 20.55, 0, 'F'),
    # top, right band: the three DCDC_DIG bulk caps together (fed by the In3 DCDC_DIG island), then 3V3 / ADC parts
    'C12': (20.65, 6.55, 90, 'F'), 'C13': (20.65, 10.0, 90, 'F'), 'C11': (20.65, 13.45, 90, 'F'), 'C8': (20.65, 15.9, 0, 'F'),
    'C21': (20.65, 17.4, 0, 'F'), 'FB1': (20.65, 18.9, 0, 'F'), 'FB2': (20.65, 20.4, 0, 'F'),
    # bottom, left band
    'U2': (2.25, 6.6, 90, 'B'), 'C4': (2.25, 9.2, 0, 'B'), 'D1': (2.25, 11.65, 90, 'B'), 'C5': (2.25, 14.0, 0, 'B'),
    'U3': (2.25, 16.6, 90, 'B'), 'R1': (2.25, 19.3, 0, 'B'),
    # bottom, right band: flash and its pull-ups, USB VBUS cap, status LED
    'U4': (20.6, 7.5, 90, 'B'), 'R6': (20.65, 10.6, 0, 'B'), 'R7': (20.65, 12.1, 0, 'B'), 'R8': (20.65, 13.6, 0, 'B'),
    'C50': (20.65, 15.1, 0, 'B'), 'C3': (20.65, 16.6, 0, 'B'), 'D2': (20.65, 18.1, 0, 'B'), 'R21': (20.65, 19.6, 0, 'B'),
    # bottom, top band: pogo pads (SWDIO, SWCLK, RESET#, BOOT#, SAI4_MCLK)
    'TP1': (5.0, 20.6, 0, 'B'), 'TP2': (6.7, 20.6, 0, 'B'), 'TP3': (8.4, 20.6, 0, 'B'), 'TP4': (10.1, 20.6, 0, 'B'),
    'TP5': (11.8, 20.6, 0, 'B'),
}

def add_parts(b):
    nets = {}
    def net(n):
        if n not in nets:
            ni = pcbnew.NETINFO_ITEM(b, n); b.Add(ni); nets[n] = ni
        return nets[n]
    fps = {}
    for key, d in design.items():
        ref = key.split('.')[0]
        if ref.startswith('#') or ref in fps: continue
        info = fpinfo[ref]
        fp = load_fp(info['fp']); fp.SetReference(ref); fp.SetValue(info['value'])
        pins = u1nets if d['pins'] == 'U1' else d['pins']
        for pad in fp.Pads():
            n = pins.get(pad.GetNumber())
            if n: pad.SetNet(net(n))
        b.Add(fp); fps[ref] = fp
    return fps, net

def tighten_courtyard(fp, hw, hh):
    """replace a footprint's courtyard with a body + 0.15 mm rectangle (call while the footprint is still at the origin)"""
    lay = None
    for g in list(fp.GraphicalItems()):
        if g.GetLayer() in (pcbnew.F_CrtYd, pcbnew.B_CrtYd): lay = g.GetLayer(); fp.Remove(g)
    for a, c in (((-hw, -hh), (hw, -hh)), ((hw, -hh), (hw, hh)), ((hw, hh), (-hw, hh)), ((-hw, hh), (-hw, -hh))):
        sh = pcbnew.FP_SHAPE(fp); sh.SetShape(pcbnew.SHAPE_T_SEGMENT); sh.SetLayer(lay or pcbnew.F_CrtYd)
        sh.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); sh.SetEnd(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
        sh.SetStart0(sh.GetStart()); sh.SetEnd0(sh.GetEnd()); sh.SetWidth(MM(0.05)); fp.Add(sh)
    fp.BuildCourtyardCaches()

def courtyard_box(fp):
    lay = pcbnew.B_CrtYd if fp.GetLayer() == pcbnew.B_Cu else pcbnew.F_CrtYd
    bb = fp.GetCourtyard(lay).BBox()
    return (pcbnew.ToMM(bb.GetLeft()) - 100, 122 - pcbnew.ToMM(bb.GetBottom()), pcbnew.ToMM(bb.GetRight()) - 100, 122 - pcbnew.ToMM(bb.GetTop()))

def pack_band(fps, refs, y0, gap=0.08):
    """stack parts along y (card frame) from y0 upward with `gap` between courtyards, keeping each part's x"""
    for r in refs:
        fp = fps[r]; x0, ya, x1, yb = courtyard_box(fp); cx, cy = card(fp.GetPosition())
        dy = (y0 - ya); fp.SetPosition(P(cx, cy + dy)); y0 = yb + dy + gap
    assert y0 < 21.7, f'band {refs} overflows: ends at {y0:.2f}'

def place(fp, x, y, rot, side):
    fp.SetPosition(P(x, y)); fp.SetOrientationDegrees(rot)
    if side == 'B': fp.Flip(fp.GetPosition(), False)


# ------------------------------------------------------------------ fan-out + under-BGA 0402s
import re
import numpy as np
from scipy.optimize import linear_sum_assignment
PLANE_NETS = {'GND', '+3V3', 'DCDC_DIG', 'DCDC_ANA'}          # nets with copper on an inner plane layer
POWER_W = {'GND': 0.2, '+3V3': 0.2, 'DCDC_DIG': 0.25, 'DCDC_ANA': 0.2}

def key(x, y): return (round(x, 2), round(y, 2))

def fanout(b, fps, net):
    u1 = fps['U1']
    balls = {}                                    # ball -> (x, y, netname) in card mm
    for pad in u1.Pads():
        n = pad.GetNetname()
        if n: x, y = card(pad.GetPosition()); balls[pad.GetNumber()] = (x, y, n)
    sites = {}                                    # key -> (x, y)
    for x, y, n in balls.values():
        for dx in (-0.4, 0.4):
            for dy in (-0.4, 0.4): sites[key(x + dx, y + dy)] = (round(x + dx, 2), round(y + dy, 2))
    # also every interstitial point of the BGA field (for extra vias under the 0402s)
    xs = sorted({k[0] for k in sites}); ys = sorted({k[1] for k in sites})
    for x in np.arange(U1_C[0] - 7.6, U1_C[0] + 7.61, 0.8):
        for y in np.arange(U1_C[1] - 7.6, U1_C[1] + 7.61, 0.8): sites.setdefault(key(float(x), float(y)), (round(float(x), 2), round(float(y), 2)))
    def adj(bx, by): return [key(bx + dx, by + dy) for dx in (-0.4, 0.4) for dy in (-0.4, 0.4)]
    via_at = {}                                   # site key -> net
    ball_via = {}                                 # ball -> site key
    bynet = {}
    for bn, (x, y, n) in balls.items(): bynet.setdefault(n, []).append(bn)
    # 1) multi-ball nets: greedy set cover with shared vias
    for n in sorted(bynet, key=lambda n: -len(bynet[n])):
        todo = set(bynet[n])
        if len(todo) < 2: continue
        while todo:
            best = None
            for bn in todo:
                for k in adj(*balls[bn][:2]):
                    if k in via_at and via_at[k] != n: continue
                    cov = [c for c in todo if k in adj(*balls[c][:2])]
                    score = (len(cov), -abs(sites[k][1] - U1_C[1]))
                    if best is None or score > best[0]: best = (score, k, cov)
            _, k, cov = best; via_at[k] = n
            for c in cov: ball_via[c] = k; todo.discard(c)
    # 2) single-ball nets: Hungarian on the free sites, biased toward the fingers / outward
    # signal balls on the outer two rings escape on F.Cu straight from the pad: no dogbone via, so the
    # channels between them stay open (the router adds a via later only if the net needs another layer)
    cap_nets0 = set()
    for ref, d in json.load(open(os.path.join(DATA, 'design_nets.json'))).items():
        if '0402' in fpinfo.get(ref.split('.')[0], {}).get('fp', '') and isinstance(d['pins'], dict):
            cap_nets0 |= set(d['pins'].values())
    ROWS = 'ABCDEFGHJKLMNPRTU'
    def ring(bn): ri, c = ROWS.index(bn[0]), int(bn[1:]); return min(ri, 16 - ri, c - 1, 17 - c)
    singles = [bn for n, l in bynet.items() if len(l) == 1 for bn in l
               if not (ring(bn) <= 1 and n not in cap_nets0 and n not in PLANE_NETS)]
    free = [k for k in sites if k not in via_at]
    C = np.full((len(singles), len(free)), 1e6)
    edge_nets = set(json.load(open(os.path.join(DATA, 'design_nets.json')))['J1']['pins'].values())
    for i, bn in enumerate(singles):
        bx, by, n = balls[bn]
        for j, k in enumerate(free):
            sx, sy = sites[k]
            if abs(sx - bx) > 0.45 or abs(sy - by) > 0.45: continue
            c = 1.0
            if n in edge_nets: c += 0.5 * (sy - by)              # prefer the finger side
            else: c += 0.3 * (abs(sx - U1_C[0]) < abs(bx - U1_C[0]))   # prefer outward
            C[i, j] = c
    # nets that need an under-BGA 0402 (non-plane nets): prefer sites with free orthogonal neighbours
    cap_nets = set()
    for ref, d in json.load(open(os.path.join(DATA, 'design_nets.json'))).items():
        if '0402' in fpinfo.get(ref.split('.')[0], {}).get('fp', '') and isinstance(d['pins'], dict):
            cap_nets |= {n for n in d['pins'].values() if n not in PLANE_NETS}
    for i, bn in enumerate(singles):
        if balls[bn][2] not in cap_nets: continue
        for j, k in enumerate(free):
            if C[i, j] >= 1e5: continue
            sx, sy = sites[k]
            nb = [key(sx + dx, sy + dy) for dx, dy in ((0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8))]
            C[i, j] -= 0.4 * sum(1 for q in nb if q in sites and q not in via_at)
    r, c = linear_sum_assignment(C)
    assert C[r, c].max() < 1e5, 'fan-out: a ball has no free via site'
    for i, j in zip(r, c):
        via_at[free[j]] = balls[singles[i]][2]; ball_via[singles[i]] = free[j]
    # write vias and dogbone tracks
    for k, n in via_at.items(): add_via(b, sites[k], net(n))
    for bn, k in ball_via.items():
        x, y, n = balls[bn]; add_track(b, (x, y), sites[k], 'F.Cu', net(n), POWER_W.get(n, TRACK))
    return balls, sites, via_at

def add_via(b, xy, ni):
    v = pcbnew.PCB_VIA(b); v.SetPosition(P(*xy)); v.SetDrill(MM(VIA_DRILL)); v.SetWidth(MM(VIA_D))
    v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni); b.Add(v); return v
def add_track(b, a, c, layer, ni, w):
    t = pcbnew.PCB_TRACK(b); t.SetStart(P(*a)); t.SetEnd(P(*c)); t.SetWidth(MM(w))
    t.SetLayer(b.GetLayerID(layer)); t.SetNet(ni); b.Add(t); return t

def bottom_keepouts(fps): return side_keepouts(fps, pcbnew.B_Cu)
def side_keepouts(fps, layer):
    boxes = []
    for ref, fp in fps.items():
        if fp.GetLayer() != layer or '0402' in fpinfo[ref]['fp'] or ref == 'U1': continue
        bb = fp.GetBoundingBox(False, False)
        x0, y1 = card(pcbnew.VECTOR2I(bb.GetLeft(), bb.GetTop())); x1, y0 = card(pcbnew.VECTOR2I(bb.GetRight(), bb.GetBottom()))
        boxes.append((x0 - 0.1, y0 - 0.1, x1 + 0.1, y1 + 0.1))
    return boxes

def place_0402(b, fps, net, balls, sites, via_at):
    ball_xy = {bn: (x, y) for bn, (x, y, n) in balls.items()}
    keep = bottom_keepouts(fps)
    used = set()
    jobs = []; free_jobs = []
    def is_decoupling(ref, na, nb):
        return ref.startswith('C') and nb == 'GND' and na not in ('DCDC_PSWITCH',)
    for ref, fp in fps.items():
        if '0402' not in fpinfo[ref]['fp']: continue
        pads = {p.GetNumber(): p.GetNetname() for p in fp.Pads()}
        na, nb = pads['1'], pads['2']
        if nb != 'GND' and na == 'GND': na, nb = nb, na
        note = fpinfo[ref]['fields'].get('Note', '')
        m = re.search(r'under ([A-U]\d+)', note)
        if m: tx, ty = ball_xy[m.group(1)]
        else:
            cand = [ball_xy[bn] for bn, (x, y, n) in balls.items() if n == na] or [ball_xy[bn] for bn, (x, y, n) in balls.items() if n == nb]
            tx, ty = cand[0] if len(cand) == 1 else (U1_C[0], U1_C[1])
            if len(cand) > 1:            # rail with many balls: aim at the ball nearest the BGA centre
                tx, ty = min(cand, key=lambda c: math.dist(c, U1_C))
        prio = (0 if na not in PLANE_NETS else 2) + (0 if m else 1)
        if not is_decoupling(ref, na, nb): free_jobs.append((ref, fp, na, nb, (tx, ty))); continue
        jobs.append((prio, ref, fp, na, nb, (tx, ty)))
    from scipy.optimize import milp, LinearConstraint, Bounds
    from scipy.sparse import lil_matrix
    def site_kind(k, n):
        """how net n can use site k: 'via' (existing via of n), 'new' (plane net, free site), ('link', src)"""
        if k in via_at: return 'via' if via_at[k] == n else None
        if n in PLANE_NETS: return 'new'
        x, y = sites[k]
        for dx, dy in ((0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8)):
            k2 = key(x + dx, y + dy)
            if via_at.get(k2) == n: return ('link', k2)
        return None
    cands = []                                     # (job index, k1, kind1, k2, kind2, cx, cy, hx, hy, dx, cost)
    for ji, (prio, ref, fp, na, nb, (tx, ty)) in enumerate(jobs):
        rad = 2.6 if prio % 2 == 0 else 6.0
        for k1, (x1, y1) in sites.items():
            if math.dist((x1, y1), (tx, ty)) > rad: continue
            t1 = site_kind(k1, na)
            if t1 is None: continue
            for dx, dy in ((0.8, 0), (-0.8, 0), (0, 0.8), (0, -0.8)):
                k2 = key(x1 + dx, y1 + dy)
                if k2 not in sites: continue
                t2 = site_kind(k2, nb)
                if t2 is None or (isinstance(t1, tuple) and t1[1] == k2) or (isinstance(t2, tuple) and t2[1] == k1): continue
                cx, cy = (x1 + sites[k2][0]) / 2, (y1 + sites[k2][1]) / 2
                hx, hy = (0.95, 0.5) if dx else (0.5, 0.95)
                if any(not (cx + hx < a or cx - hx > c or cy + hy < bb or cy - hy > d) for a, bb, c, d in keep): continue
                if cx - hx < U1_C[0] - 8.1 or cx + hx > U1_C[0] + 8.1 or cy - hy < U1_C[1] - 8.1 or cy + hy > U1_C[1] + 8.1: continue
                cost = math.dist((cx, cy), (tx, ty)) + 0.3 * ((t1 != 'via') + (t2 != 'via'))
                cands.append((ji, k1, t1, k2, t2, cx, cy, hx, hy, dx, cost))
    nC = len(cands); nJ = len(jobs)
    site_idx = {k: i for i, k in enumerate(sites)}
    def touched(c):
        ks = {c[1], c[3]}
        for t in (c[2], c[4]):
            if isinstance(t, tuple): ks.add(t[1])
        return ks
    rows = []; lo = []; hi = []
    A = lil_matrix((nJ + len(sites), nC))
    for i, c in enumerate(cands):
        A[c[0], i] = 1
        for k in touched(c): A[nJ + site_idx[k], i] = 1
    lo = [1] * nJ + [0] * len(sites); hi = [1] * nJ + [1] * len(sites)
    # body spacing: two chosen placements must keep >= 0.2 mm between bodies
    pairs = []
    order = sorted(range(nC), key=lambda i: cands[i][5])
    for ii, i in enumerate(order):
        ci = cands[i]
        for j in order[ii + 1:]:
            cj = cands[j]
            if cj[5] - ci[5] > 2.2: break
            if ci[0] == cj[0]: continue
            if abs(ci[5] - cj[5]) < ci[7] + cj[7] - 0.25 + 0.2 and abs(ci[6] - cj[6]) < ci[8] + cj[8] - 0.25 + 0.2:
                pairs.append((i, j))
    P2 = lil_matrix((len(pairs), nC))
    for r, (i, j) in enumerate(pairs): P2[r, i] = 1; P2[r, j] = 1
    # one slack column per part ("not under a via": falls back to a routed spot) with a large penalty
    from scipy.sparse import hstack, identity, csr_matrix, vstack
    S = vstack([identity(nJ, format='csr'), csr_matrix((len(sites), nJ))])
    Afull = hstack([A.tocsr(), S]).tocsr()
    cost = np.concatenate([np.array([c[10] for c in cands]), np.full(nJ, 50.0)])
    cons = [LinearConstraint(Afull, lo, hi)]
    if pairs: cons.append(LinearConstraint(hstack([P2.tocsr(), csr_matrix((len(pairs), nJ))]).tocsr(), 0, 1))
    res = milp(cost, constraints=cons, integrality=np.ones(nC + nJ), bounds=Bounds(0, 1), options={'time_limit': 240})
    assert res.x is not None, f'0402 placement failed: {res.message}'
    chosen = [cands[i] for i in range(nC) if res.x[i] > 0.5]
    for j in range(nJ):
        if res.x[nC + j] > 0.5:
            prio, ref, fp, na, nb, t = jobs[j]; free_jobs.append((ref, fp, na, nb, t))
            print('  not over a via (will be routed):', ref, na)
    print(f'0402 placement: {len(chosen)}/{nJ} parts, {len(cands)} candidates, {len(pairs)} spacing pairs, cost {res.fun:.1f}')
    placed = []
    for c in chosen:
        ji, k1, t1, k2, t2, cx, cy, hx, hy, dx, _ = c
        prio, ref, fp, na, nb, _t = jobs[ji]
        for k, t, n in ((k1, t1, na), (k2, t2, nb)):
            if t != 'via':
                via_at[k] = n; add_via(b, sites[k], net(n))
                if isinstance(t, tuple): add_track(b, sites[t[1]], sites[k], 'B.Cu', net(n), 0.15)
        rot = 0 if dx else 90
        fp.SetPosition(P(cx, cy)); fp.SetOrientationDegrees(rot)
        if fp.GetLayer() != pcbnew.B_Cu: fp.Flip(fp.GetPosition(), False)
        p1 = [p for p in fp.Pads() if p.GetNumber() == '1'][0]
        if math.dist(card(p1.GetPosition()), sites[k1]) > 0.3: fp.SetOrientationDegrees(fp.GetOrientationDegrees() + 180)
        p1 = [p for p in fp.Pads() if p.GetNumber() == '1'][0]
        assert math.dist(card(p1.GetPosition()), sites[k1]) < 0.3, ref
        placed.append((cx, cy, hx, hy))
    # routed 0402s (straps, PSWITCH RC, DCDC_MODE, MIPI pulls): free spots under the BGA, away from every via
    vias = [sites[k] for k in via_at]; top_placed = []
    for ref, fp, na, nb, (tx, ty) in sorted(free_jobs, key=lambda j: j[0]):
        best = None
        for gx in np.arange(0.9, WIDTH - 0.89, 0.1):
            for gy in np.arange(4.0, 21.3, 0.1):
                for rot, hx, hy in ((0, 0.95, 0.5), (90, 0.5, 0.95)):
                    cx, cy = float(gx), float(gy)
                    pads = [(cx - 0.48, cy), (cx + 0.48, cy)] if rot == 0 else [(cx, cy - 0.48), (cx, cy + 0.48)]
                    phw, phh = (0.3, 0.33) if rot == 0 else (0.33, 0.3)          # pad half-size, slightly generous
                    if any(math.hypot(max(abs(px - vx) - phw, 0), max(abs(py - vy) - phh, 0)) < VIA_D / 2 + CLEAR + 0.03
                           for px, py in pads for vx, vy in vias): continue
                    if any(abs(px - cx) < phx + hx + 0.05 and abs(py - cy) < phy + hy + 0.05 for (px, py, phx, phy) in placed): continue
                    if any(not (cx + hx < a or cx - hx > c or cy + hy < bb or cy - hy > d) for a, bb, c, d in keep): continue
                    if math.dist((cx, cy), (15.0, 21.99)) < 3.0 + max(hx, hy): continue      # screw standoff on the bottom
                    if cy + hy > 21.6 or cx - hx < 0.3 or cx + hx > WIDTH - 0.3 or cy - hy < 3.85: continue
                    if cy - hy < 4.9 and (cx - hx < 1.6 or cx + hx > WIDTH - 1.6): continue      # body chamfers
                    cost = math.dist((cx, cy), (tx, ty))
                    if best is None or cost < best[0]: best = (cost, cx, cy, rot, hx, hy)
        side = 'B'
        if not best:                                  # fall back to the top side, outside the BGA courtyard
            topkeep = side_keepouts(fps, pcbnew.F_Cu) + [(U1_C[0] - 7.25, U1_C[1] - 7.25, U1_C[0] + 7.25, U1_C[1] + 7.25)]
            for gx in np.arange(0.9, WIDTH - 0.89, 0.1):
                for gy in np.arange(4.0, 21.3, 0.1):
                    for rot, hx, hy in ((0, 0.95, 0.5), (90, 0.5, 0.95)):
                        cx, cy = float(gx), float(gy)
                        if any(abs(px - cx) < phx + hx + 0.05 and abs(py - cy) < phy + hy + 0.05 for (px, py, phx, phy) in top_placed): continue
                        if any(not (cx + hx < a or cx - hx > c or cy + hy < bb or cy - hy > d) for a, bb, c, d in topkeep): continue
                        if math.dist((cx, cy), (15.0, 21.99)) < 2.3 + max(hx, hy): continue
                        if cy + hy > 21.6 or cx - hx < 0.3 or cx + hx > WIDTH - 0.3 or cy - hy < 3.85: continue
                        if cy - hy < 4.9 and (cx - hx < 1.6 or cx + hx > WIDTH - 1.6): continue
                        cost = math.dist((cx, cy), (tx, ty))
                        if best is None or cost < best[0]: best = (cost, cx, cy, rot, hx, hy)
            side = 'F'
        if not best: print('  NO SPOT', ref, na, nb); continue
        _, cx, cy, rot, hx, hy = best
        fp.SetPosition(P(cx, cy)); fp.SetOrientationDegrees(rot)
        if (fp.GetLayer() == pcbnew.B_Cu) != (side == 'B'): fp.Flip(fp.GetPosition(), False)
        (placed if side == 'B' else top_placed).append((cx, cy, hx, hy))
        if side == 'F': print('  on top side:', ref, na, round(cx, 2), round(cy, 2))
    return placed

if __name__ == '__main__':
    b = new_board(); outline(b)
    fps, net = add_parts(b)
    # tight courtyards where the stock ones are padded far past the body (BGA 1 mm, 4030 inductor, test pads)
    tighten_courtyard(fps['U1'], 7.15, 7.15); tighten_courtyard(fps['L1'], 2.15, 2.15)
    for r in fps:
        if r.startswith('TP'): tighten_courtyard(fps[r], 0.65, 0.65)
    for ref, fp in fps.items():
        if ref in PLACE: place(fp, *PLACE[ref])
        else:
            assert '0402' in fpinfo[ref]['fp'], f'{ref} has no placement'
            place(fp, -10, -10, 0, 'B')            # 0402: placed under the BGA by the fan-out step
    pack_band(fps, ['C12', 'C13', 'C11', 'C8', 'C21', 'FB1', 'FB2'], 4.85)
    pack_band(fps, ['U2', 'C4', 'D1', 'C5', 'U3', 'R1'], 4.65)
    pack_band(fps, ['R6', 'R7', 'R8', 'C50', 'C3', 'D2', 'R21'], courtyard_box(fps['U4'])[3] + 0.08)
    a1 = [p for p in fps['U1'].Pads() if p.GetNumber() == 'A1'][0]; a17 = [p for p in fps['U1'].Pads() if p.GetNumber() == 'A17'][0]
    u1 = [p for p in fps['U1'].Pads() if p.GetNumber() == 'U1'][0]
    print('U1 A1 at', [round(v, 2) for v in card(a1.GetPosition())], 'A17 at', [round(v, 2) for v in card(a17.GetPosition())],
          'U1 at', [round(v, 2) for v in card(u1.GetPosition())])
    balls, sites, via_at = fanout(b, fps, net)
    placed = place_0402(b, fps, net, balls, sites, via_at)
    print('vias', len(via_at), '0402 under BGA', len(placed))
    pcbnew.SaveBoard(OUT, b); pcbnew.SaveBoard(OUT.replace('.kicad_pcb', '-placed.kicad_pcb'), b)
    print('saved', OUT, len(fps), 'footprints (and *-placed.kicad_pcb, the input of tools/route.py)')
