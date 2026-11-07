"""Finish the connections Freerouting left open, with a grid A* router.

  python3 tools/finish_route.py            (after tools/route.py; edits rt1176-micromod-som.kicad_pcb in place)

Reads KiCad's DRC 'unconnected items' pairs and routes each pair on F.Cu / In2.Cu / In3.Cu / B.Cu (In1/In4 are planes)
on a 0.05 mm grid. Obstacles are every copper item of another net, inflated by clearance + half the track width
(tracks) or clearance + via radius (vias), so the result is DRC-clean by construction (checked again with tools/drc.py).
"""
import heapq, math, os, re, sys, tempfile
import numpy as np
import pcbnew
from matplotlib.path import Path
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from pcbgen import OUT, MM, VIA_D, VIA_DRILL, TRACK, CLEAR

G = 0.05                                   # grid (mm)
X0, Y0, NX, NY = 99.0, 99.0, 500, 480      # board mm (KiCad frame) covered by the grid
SIG = ['F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu']
VIA_COST = 40                              # in grid steps (2 mm)
MARGIN = 0.012                             # rasterisation margin (mm)

def mm(v): return pcbnew.ToMM(v)

def poly_cells(ps):
    """grid cells (ix, iy) whose centres lie inside a SHAPE_POLY_SET"""
    out = []
    for oi in range(ps.OutlineCount()):
        o = ps.Outline(oi); pts = np.array([[mm(o.CPoint(i).x), mm(o.CPoint(i).y)] for i in range(o.PointCount())])
        if len(pts) < 3: continue
        x0, y0 = pts.min(0); x1, y1 = pts.max(0)
        ix0, ix1 = max(int((x0 - X0) / G) - 1, 0), min(int((x1 - X0) / G) + 2, NX)
        iy0, iy1 = max(int((y0 - Y0) / G) - 1, 0), min(int((y1 - Y0) / G) + 2, NY)
        if ix0 >= ix1 or iy0 >= iy1: continue
        gx, gy = np.meshgrid(np.arange(ix0, ix1), np.arange(iy0, iy1), indexing='ij')
        c = np.stack([X0 + gx.ravel() * G, Y0 + gy.ravel() * G], 1)
        inside = Path(pts).contains_points(c)
        out.append(np.stack([gx.ravel()[inside], gy.ravel()[inside]], 1))
    return np.concatenate(out) if out else np.zeros((0, 2), int)

def capsule(ps, a, c, r, n=12):
    """add a stadium (segment a-c, radius r, nm) to a SHAPE_POLY_SET"""
    ang = math.atan2(c[1] - a[1], c[0] - a[0]); ps.NewOutline()
    for cx, cy, a0 in ((c[0], c[1], ang - math.pi / 2), (a[0], a[1], ang + math.pi / 2)):
        for i in range(n + 1):
            t = a0 + math.pi * i / n
            ps.Append(int(cx + r * math.cos(t)), int(cy + r * math.sin(t)))

def item_poly(item, layer, infl):
    ps = pcbnew.SHAPE_POLY_SET()
    if item.GetClass() == 'PCB_VIA':
        p = item.GetPosition(); capsule(ps, (p.x, p.y), (p.x + 1, p.y), item.GetWidth() / 2 + MM(infl))
    elif item.GetClass() == 'PCB_TRACK':
        a, c = item.GetStart(), item.GetEnd()
        capsule(ps, (a.x, a.y), (c.x + (1 if a == c else 0), c.y), item.GetWidth() / 2 + MM(infl))
    else:
        item.TransformShapeToPolygon(ps, layer, MM(infl), MM(0.005))
    return ps

def build(b):
    lid = {n: b.GetLayerID(n) for n in SIG}
    items = []                                           # (netname, layer name, item)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for n in SIG:
                if p.IsOnLayer(lid[n]): items.append((p.GetNetname(), n, p))
    for t in b.GetTracks():
        if t.GetClass() == 'PCB_VIA':
            for n in SIG: items.append((t.GetNetname(), n, t))
        elif b.GetLayerName(t.GetLayer()) in SIG: items.append((t.GetNetname(), b.GetLayerName(t.GetLayer()), t))
    return items, lid

PROTECT = None   # nets whose tracks are never ripped up (planes and power rails), set in main()

class Grid:
    """hard obstacles: pads, board edge, power-net copper. soft obstacles: signal tracks/vias (can be ripped up)."""
    def __init__(self, b):
        self.b = b; self.items, self.lid = build(b)
        self.hT = np.zeros((4, NX, NY), np.int32); self.hV = np.zeros((4, NX, NY), np.int32)
        self.sT = np.zeros((4, NX, NY), np.int32); self.sV = np.zeros((4, NX, NY), np.int32)
        self.own = {}                                    # net -> [(hard?, li, kind, cells)]
        self.soft_items = {}                             # net -> [item]
        self.soft_cells = {}                             # net -> set of flat T-cell indices (li, x, y)
        for net, ln, it in self.items: self.add(net, ln, it)
        ps = pcbnew.SHAPE_POLY_SET(); b.GetBoardPolygonOutlines(ps)
        for kind, d in (('T', 0.25 + TRACK / 2 + MARGIN), ('V', 0.25 + VIA_D / 2 + MARGIN)):
            q = pcbnew.SHAPE_POLY_SET(ps); q.Deflate(MM(d), 16)
            ok = np.zeros((NX, NY), bool); c = poly_cells(q); ok[c[:, 0], c[:, 1]] = True
            (self.hT if kind == 'T' else self.hV)[:, ~ok] += 1000
    def is_soft(self, net, it):
        return it.GetClass() in ('PCB_TRACK', 'PCB_VIA') and net and net not in PROTECT
    def add(self, net, ln, it, sign=1):
        li = SIG.index(ln); L = self.lid[ln]; soft = self.is_soft(net, it)
        if soft and sign > 0 and (li == 0 or it.GetClass() != 'PCB_VIA'):
            self.soft_items.setdefault(net, []).append(it)
        for kind, infl in (('T', CLEAR + TRACK / 2 + MARGIN), ('V', CLEAR + VIA_D / 2 + MARGIN)):
            c = poly_cells(item_poly(it, L, infl))
            arr = (self.sT if kind == 'T' else self.sV) if soft else (self.hT if kind == 'T' else self.hV)
            np.add.at(arr[li], (c[:, 0], c[:, 1]), sign)
            if sign > 0:
                self.own.setdefault(net, []).append((soft, li, kind, c, it))
                if soft and kind == 'T':
                    self.soft_cells.setdefault(net, set()).update((li * NX + c[:, 0]) * NY + c[:, 1])
    def rip(self, net):
        """delete a net's tracks and vias from the board and the grid"""
        keep = []
        for soft, li, kind, c, it in self.own.get(net, []):
            if not soft: keep.append((soft, li, kind, c, it)); continue
            np.add.at((self.sT if kind == 'T' else self.sV)[li], (c[:, 0], c[:, 1]), -1)
        self.own[net] = keep
        for it in self.soft_items.pop(net, []): self.b.Remove(it)
        self.soft_cells.pop(net, None)
    def masks(self, net):
        hT = self.hT.copy(); hV = self.hV.copy(); sT = self.sT.copy(); sV = self.sV.copy()
        for soft, li, kind, c, it in self.own.get(net, []):
            arr = (sT if kind == 'T' else sV) if soft else (hT if kind == 'T' else hV)
            np.add.at(arr[li], (c[:, 0], c[:, 1]), -1)
        return hT > 0, (hV > 0).any(0), sT > 0, (sV > 0).any(0)

def cells_of(g, it, layers):
    out = set()
    for ln in layers:
        li = SIG.index(ln)
        for ix, iy in poly_cells(item_poly(it, g.lid[ln], 0)): out.add((li, int(ix), int(iy)))
    return out

def astar(Tb, Vb, src, dst, sT=None, sV=None, hist=None, soft_cost=12.0):
    """A* over (layer, x, y). With sT/sV given, other signal nets' copper is passable at soft_cost (+history) per cell."""
    dx = [1, -1, 0, 0, 1, 1, -1, -1]; dy = [0, 0, 1, -1, 1, -1, 1, -1]
    cost8 = [1, 1, 1, 1, 1.414, 1.414, 1.414, 1.414]
    dl = np.array([list(d) for d in dst]); tx, ty = dl[:, 1].mean(), dl[:, 2].mean()
    def h(ix, iy): return math.hypot(ix - tx, iy - ty) * 0.9
    rip = sT is not None
    if not rip: sT = np.zeros_like(Tb); sV = np.zeros_like(Vb)
    best = {}; prev = {}; pq = []
    for s_ in src:
        if Tb[s_]: continue
        best[s_] = 0; heapq.heappush(pq, (h(s_[1], s_[2]), 0, s_))
    while pq:
        f, gc, s_ = heapq.heappop(pq)
        if gc > best.get(s_, 1e18): continue
        if s_ in dst:
            path = [s_]
            while path[-1] in prev: path.append(prev[path[-1]])
            return path[::-1]
        li, ix, iy = s_
        for k in range(8):
            nx, ny = ix + dx[k], iy + dy[k]
            if not (0 <= nx < NX and 0 <= ny < NY) or Tb[li, nx, ny]: continue
            if k >= 4 and (Tb[li, nx, iy] or Tb[li, ix, ny]): continue
            if not rip and (sT[li, nx, ny] or (k >= 4 and (sT[li, nx, iy] or sT[li, ix, ny]))): continue
            c = gc + cost8[k]
            if rip and sT[li, nx, ny]: c += soft_cost + hist[li, nx, ny]
            n = (li, nx, ny)
            if c < best.get(n, 1e18): best[n] = c; prev[n] = s_; heapq.heappush(pq, (c + h(nx, ny), c, n))
        if not Vb[ix, iy] and (rip or not sV[ix, iy]):
            for l2 in range(4):
                if l2 == li or Tb[l2, ix, iy] or (not rip and sT[l2, ix, iy]): continue
                c = gc + VIA_COST + (soft_cost * 4 if rip and sV[ix, iy] else 0)
                n = (l2, ix, iy)
                if c < best.get(n, 1e18): best[n] = c; prev[n] = s_; heapq.heappush(pq, (c + h(ix, iy), c, n))
    return None

def emit(b, g, net, path):
    ni = b.FindNet(net); added = []
    def P(ix, iy): return pcbnew.VECTOR2I(MM(float(X0 + int(ix) * G)), MM(float(Y0 + int(iy) * G)))
    i = 0
    segs = []                                # (layer, start, end)
    start = path[0]; lastdir = None
    for a, c in zip(path, path[1:]):
        if a[0] != c[0]:                     # via
            if (start[1], start[2]) != (a[1], a[2]): segs.append((a[0], start, a))
            v = pcbnew.PCB_VIA(b); v.SetPosition(P(a[1], a[2])); v.SetDrill(MM(VIA_DRILL)); v.SetWidth(MM(VIA_D))
            v.SetViaType(pcbnew.VIATYPE_THROUGH); v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(ni); b.Add(v); added.append(v)
            start = c; lastdir = None; continue
        d = (c[1] - a[1], c[2] - a[2])
        if lastdir is not None and d != lastdir: segs.append((a[0], start, a)); start = a
        lastdir = d
    if (start[1], start[2]) != (path[-1][1], path[-1][2]): segs.append((path[-1][0], start, path[-1]))
    for li, s, e in segs:
        t = pcbnew.PCB_TRACK(b); t.SetStart(P(s[1], s[2])); t.SetEnd(P(e[1], e[2])); t.SetWidth(MM(TRACK))
        t.SetLayer(g.lid[SIG[li]]); t.SetNet(ni); b.Add(t); added.append(t)
    for it in added:
        if it.GetClass() == 'PCB_VIA':
            for ln in SIG: g.add(net, ln, it)
        else: g.add(net, b.GetLayerName(it.GetLayer()), it)
    return len(segs), sum(1 for it in added if it.GetClass() == 'PCB_VIA')

def unconnected(b):
    rpt = os.path.join(tempfile.mkdtemp(), 'drc.txt')
    pcbnew.WriteDRCReport(b, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
    pairs = []
    for blk in re.split(r'\n(?=\[)', open(rpt).read()):
        if not blk.startswith('[unconnected_items]'): continue
        pairs.append(re.findall(r'@\(([\d.]+) mm, ([\d.]+) mm\): (.*)', blk))
    return pairs

def find_item(b, x, y, desc):
    m = re.match(r'Pad (\S+) \[(.*?)\] of (\S+)', desc)
    if m:
        fp = b.FindFootprintByReference(m.group(3))
        return [p for p in fp.Pads() if p.GetNumber() == m.group(1)][0], m.group(2)
    m = re.match(r'(Track|Via) \[(.*?)\]', desc); net = m.group(2)
    best = None
    for t in b.GetTracks():
        if t.GetNetname() != net or (t.GetClass() == 'PCB_VIA') != (m.group(1) == 'Via'): continue
        d = min(math.dist((mm(t.GetStart().x), mm(t.GetStart().y)), (x, y)), math.dist((mm(t.GetEnd().x), mm(t.GetEnd().y)), (x, y)))
        if best is None or d < best[0]: best = (d, t)
    return best[1], net

def layers_of(b, it):
    if it.GetClass() == 'PCB_VIA': return SIG
    if it.GetClass() == 'PCB_TRACK': return [b.GetLayerName(it.GetLayer())]
    return [n for n in SIG if it.IsOnLayer(b.GetLayerID(n))]

def main():
    global PROTECT
    from route import POWER_CLASS
    from pcbgen import PLANE_NETS
    PROTECT = set(POWER_CLASS) | set(PLANE_NETS)
    b = pcbnew.LoadBoard(OUT)
    hist = np.zeros((4, NX, NY), np.float32)
    for it_no in range(int(os.environ.get('ITERS', 25))):
        pairs = unconnected(b)
        print(f'iteration {it_no}: {len(pairs)} open connections'); sys.stdout.flush()
        if not pairs: break
        g = Grid(b); ripped = set()
        for pr in pairs:
            (xa, ya, da), (xb, yb, db) = pr[:2]
            try:
                a, net = find_item(b, float(xa), float(ya), da); c, _ = find_item(b, float(xb), float(yb), db)
            except Exception as e:
                print('  skip (item gone)', da, db); continue
            if net in ripped: continue                 # routed again next iteration
            hT, hV, sT, sV = g.masks(net)
            src = cells_of(g, a, layers_of(b, a)); dst = cells_of(g, c, layers_of(b, c))
            path = astar(hT | sT, hV | sV, src, dst)
            mode = 'clean'
            if not path:
                path = astar(hT, hV, src, dst, sT, sV, hist); mode = 'rip-up'
                if not path: print('  FAIL', net, da, '->', db); continue
                hit = set()
                flat = {(l * NX + x) * NY + y for l, x, y in path}
                for n2, cells in list(g.soft_cells.items()):
                    if n2 != net and flat & cells: hit.add(n2)
                for l, x, y in path:
                    if sT[l, x, y]: hist[l, x, y] += 6.0          # PathFinder history: contested cells get dearer
                for n2 in hit: g.rip(n2); ripped.add(n2)
                mode += ' ' + ','.join(sorted(hit))
            ns, nv = emit(b, g, net, path)
            print(f'  {net}: {ns} segs, {nv} vias ({mode})'); sys.stdout.flush()
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    pcbnew.SaveBoard(OUT, b)
    left = unconnected(b)
    print('saved;', len(left), 'open connections left')

if __name__ == '__main__':
    main()
