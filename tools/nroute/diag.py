"""Diagnostics for nroute: per-net reachability on the hard maps and a picture of the conflicts.
  python3 tools/nroute/diag.py NET        flood-fill each terminal of NET through the fixed obstacles
  python3 tools/nroute/diag.py --map      build/nroute/conflicts.png (fixed copper grey, conflict cells red)"""
import os, sys, collections
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE)); W = os.path.join(ROOT, 'build', 'nroute')
NX, NY, NL, NN = map(int, open(os.path.join(W, 'header.txt')).read().split())
hardT = np.fromfile(os.path.join(W, 'hardT.i16'), np.int16).reshape(NL, NX, NY)
hardV = np.fromfile(os.path.join(W, 'hardV.i16'), np.int16).reshape(NX, NY)
fixedvia = np.fromfile(os.path.join(W, 'fixedvia.i16'), np.int16).reshape(NX, NY)
holeblock = np.fromfile(os.path.join(W, 'holeblock.u8'), np.uint8).reshape(NX, NY)
nets = []; lines = open(os.path.join(W, 'nets.txt')).read().split('\n'); i = 0
while i < len(lines) and lines[i]:
    name, nt = lines[i].split()[:2]; terms = []
    for t in range(int(nt)):
        v = list(map(int, lines[i + 1 + t].split())); terms.append([tuple(v[1 + 3 * k: 4 + 3 * k]) for k in range(v[0])])
    nets.append((name, terms)); i += 1 + int(nt)
def card(x, y): return round(99 + x * 0.05 - 100, 2), round(122 - (99 + y * 0.05), 2)
if sys.argv[1] == '--map':
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 4, figsize=(28, 8))
    conf = [l.split() for l in open(os.path.join(W, 'conflicts.txt')) if l.strip()]
    for li in range(4):
        img = np.ones((NY, NX, 3)); img[(hardT[li] == -2).T] = (0.75, 0.75, 0.75); img[(hardT[li] >= 0).T] = (0.6, 0.8, 1.0)
        for n, l, x, y in conf:
            if int(l) in (li, 9): img[int(y), int(x)] = (1, 0, 0) if int(l) == li else (1, 0, 1)
        ax[li].imshow(img[40:480, 0:480]); ax[li].set_title(['F.Cu', 'In2.Cu', 'In3.Cu', 'B.Cu'][li]); ax[li].axis('off')
    plt.tight_layout(); plt.savefig(os.path.join(W, 'conflicts.png'), dpi=110)
    print(collections.Counter(c[0] for c in conf).most_common(40))
else:
    ni = [n for n, _ in nets].index(sys.argv[1]); terms = nets[ni][1]
    for ti, t in enumerate(terms):
        seen = set(c for c in t if hardT[c] in (-1, ni)); dq = collections.deque(seen); vias = 0
        while dq:
            l, x, y = dq.popleft()
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (l, x + dx, y + dy)
                if 0 <= n[1] < NX and 0 <= n[2] < NY and n not in seen and hardT[n] in (-1, ni): seen.add(n); dq.append(n)
            if fixedvia[x, y] == ni or (hardV[x, y] in (-1, ni) and not holeblock[x, y]): vias += 1
            if len(seen) > 20000: break
        ls = collections.Counter(c[0] for c in t)
        print(f'terminal {ti}: layers {dict(ls)} at card {card(t[0][1], t[0][2])}: {len(t)} cells, {sum(1 for c in t if hardT[c] in (-1, ni))} usable; reaches {len(seen)} cells on its layer, {vias} via spots')
