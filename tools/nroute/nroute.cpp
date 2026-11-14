// Negotiated-congestion (PathFinder) grid router for the RT1176 MicroMod card.
//
//   g++ -O2 -std=c++17 -o build/nroute/nroute tools/nroute/nroute.cpp
//   build/nroute/nroute build/nroute [max_iters]
//
// Grid: 0.05 mm, 4 signal layers (F.Cu, In2.Cu, In3.Cu, B.Cu), through vias only. Tracks are 0.09 mm wide with
// 0.09 mm clearance; vias are 0.3/0.15 mm. Fixed copper comes pre-rasterised from prep.py (hardT/hardV).
//
// Every net is routed by A* over (layer, x, y). Nets may at first share space; a shared cell costs more each
// round (present-sharing factor) and keeps a memory of having been fought over (history), so nets with an
// alternative move away and the ones that truly need a spot keep it. Each round rips up and re-routes every net.
//
// Spacing model ("fat wires"): each net blocks, for other nets,
//   track centres within sqrt(14) cells of its track centres on the same layer   (0.184 mm >= 0.09 + 0.09),
//   track centres within sqrt(35) cells of its vias on every layer                (0.29 mm: hole wall + 0.17 + w/2),
//   via centres within sqrt(35) cells of its track centres on any layer,
//   via centres within 8 cells of its vias                                        (0.40 mm hole-to-hole).
// The square-root thresholds include the half-step a segment can sag between two grid points.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <queue>
#include <string>
#include <vector>
using namespace std;

static int NX, NY, NL, N2;                 // N2 = NX*NY
static vector<int16_t> hardT, hardV, fixedvia;
static vector<uint8_t> holeblock, mask3v3, frozenT, frozenV;
static vector<uint16_t> occT, occV;        // number of nets blocking a track centre / via centre here
static vector<float> histT, histV;
static vector<uint32_t> markT, markV;      // scratch for distinct stamping
static uint32_t stampId = 1;

struct Off { int dx, dy; };
static vector<Off> discTT, discTV, discVV, discHist, discTTw, discTVw, discWide;
static void makeDisc(vector<Off>& d, int lim2) {           // offsets with dx^2+dy^2 < lim2
    int r = (int)ceil(sqrt((double)lim2));
    for (int dx = -r; dx <= r; dx++) for (int dy = -r; dy <= r; dy++) if (dx * dx + dy * dy < lim2) d.push_back({dx, dy});
}

struct Net {
    string name;
    vector<vector<int>> terms;             // node ids (l*N2 + x*NY + y)
    vector<vector<int>> paths;
    vector<int> tcells;                    // nodes used by routed track
    vector<int> vias;                      // 2-D cells of new vias
    bool failed = false;
    bool wide = false;                     // reserve room for a 0.25 mm track (plane stubs of the power fingers)
    bool crit = false;                     // routed first, then frozen: everything else goes around it
    int kind = 0;                          // 0 normal; 1 stub to any new via (GND); 2 stub to a new via outside the DCDC_DIG island (+3V3)
};
static vector<Net> nets;

static inline int nodeL(int n) { return n / N2; }
static inline int nodeC(int n) { return n % N2; }

// add (sign=+1) or remove (sign=-1) a net's blocked set from the occupancy maps; sign=0 writes it into the frozen maps
static void contribute(const Net& net, int sign) {
    stampId++;
    const vector<Off>& dTT = net.wide ? discTTw : discTT; const vector<Off>& dTVt = net.wide ? discTVw : discTV;
    for (int n : net.tcells) {
        int l = nodeL(n), c = nodeC(n), x = c / NY, y = c % NY;
        for (auto& o : dTT) {
            int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue;
            int i = l * N2 + xx * NY + yy;
            if (markT[i] != stampId) { markT[i] = stampId; if (sign) occT[i] += sign; else frozenT[i] = 1; }
        }
    }
    for (int c : net.vias) {
        int x = c / NY, y = c % NY;
        for (auto& o : discTV) {
            int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue;
            for (int l = 0; l < NL; l++) { int i = l * N2 + xx * NY + yy; if (markT[i] != stampId) { markT[i] = stampId; if (sign) occT[i] += sign; else frozenT[i] = 1; } }
        }
    }
    for (int n : net.tcells) {
        int c = nodeC(n), x = c / NY, y = c % NY;
        for (auto& o : dTVt) {
            int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue;
            int i = xx * NY + yy;
            if (markV[i] != stampId) { markV[i] = stampId; if (sign) occV[i] += sign; else frozenV[i] = 1; }
        }
    }
    for (int c : net.vias) {
        int x = c / NY, y = c % NY;
        for (auto& o : discVV) {
            int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue;
            int i = xx * NY + yy;
            if (markV[i] != stampId) { markV[i] = stampId; if (sign) occV[i] += sign; else frozenV[i] = 1; }
        }
    }
}

// search state
static vector<float> gcost; static vector<uint32_t> gstamp, tgtStamp, treeStamp, ownViaStamp, ownViaBlockStamp;
static vector<int> parent; static vector<int8_t> pdir; static vector<int16_t> tgtIdx;
static uint32_t searchId = 0, treeId = 0;
static double VIA_CONF = 8.0, CRIT_VIA = 6.0;
static bool HARD = false;                 // finishing mode: other nets' space is forbidden, not just expensive
static double PRES = 0.5, VIA_BASE = 24.0, TURN = 0.3, HWEIGHT = 1.15;
static const int DX[8] = {1, -1, 0, 0, 1, 1, -1, -1}, DY[8] = {0, 0, 1, -1, 1, -1, 1, -1};
static const float DL[8] = {1, 1, 1, 1, 1.41421f, 1.41421f, 1.41421f, 1.41421f};

static bool routeNet(int ni) {
    Net& net = nets[ni];
    net.paths.clear(); net.tcells.clear(); net.vias.clear(); net.failed = false;
    int nt = net.terms.size(); if (nt < 2 && !net.kind) return true;
    const int VGOAL = NL * N2;             // virtual goal node of a stub: 'a new via here'
    treeId++;
    vector<char> reached(nt, 0);
    vector<int> tree;
    auto addTree = [&](int n) { if (treeStamp[n] != treeId) { treeStamp[n] = treeId; tree.push_back(n); } };
    for (int n : net.terms[0]) addTree(n);
    reached[0] = 1; int left = net.kind ? 1 : nt - 1;
    // bounding boxes of terminals
    vector<array<int, 4>> bb(nt);
    for (int t = 0; t < nt; t++) {
        int x0 = 1e9, x1 = -1, y0 = 1e9, y1 = -1;
        for (int n : net.terms[t]) { int c = nodeC(n), x = c / NY, y = c % NY; x0 = min(x0, x); x1 = max(x1, x); y0 = min(y0, y); y1 = max(y1, y); }
        bb[t] = {x0, x1, y0, y1};
    }
    while (left > 0) {
        searchId++;
        for (int t = 0; t < nt; t++) if (!reached[t]) for (int n : net.terms[t]) { tgtStamp[n] = searchId; tgtIdx[n] = t; }
        auto heur = [&](int x, int y) {
            if (net.kind) return 0.0f;
            float best = 1e30f;
            for (int t = 0; t < nt; t++) if (!reached[t]) {
                int dx = max(0, max(bb[t][0] - x, x - bb[t][1])), dy = max(0, max(bb[t][2] - y, y - bb[t][3]));
                float h = (float)(max(dx, dy) + 0.41421f * min(dx, dy));
                best = min(best, h);
            }
            return best * (float)HWEIGHT;
        };
        typedef pair<float, int> QE;
        priority_queue<QE, vector<QE>, greater<QE>> pq;
        for (int n : tree) {
            if (hardT[n] != -1 && hardT[n] != ni) continue;
            gcost[n] = 0; gstamp[n] = searchId; parent[n] = -1; pdir[n] = -1;
            int c = nodeC(n); pq.push({heur(c / NY, c % NY), n});
        }
        int goal = -1;
        while (!pq.empty()) {
            auto [f, n] = pq.top(); pq.pop();
            if (n == VGOAL) { goal = n; break; }
            float g = gcost[n];
            int c = nodeC(n), l = nodeL(n), x = c / NY, y = c % NY;
            if (f > g + heur(x, y) + 1e-3f) continue;                    // stale entry
            if (tgtStamp[n] == searchId) { goal = n; break; }
            for (int k = 0; k < 8; k++) {
                int xx = x + DX[k], yy = y + DY[k]; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue;
                int m = l * N2 + xx * NY + yy;
                if (hardT[m] != -1 && hardT[m] != ni) continue;
                if (!net.crit && frozenT[m]) continue;
                if (HARD && occT[m]) continue;
                if (net.wide) { bool ok = true; for (auto& o : discWide) { int x2 = xx + o.dx, y2 = yy + o.dy; if (x2 < 0 || y2 < 0 || x2 >= NX || y2 >= NY) { ok = false; break; } int q = l * N2 + x2 * NY + y2; if (hardT[q] != -1 && hardT[q] != ni) { ok = false; break; } } if (!ok) continue; }
                float step = DL[k] * (1.0f + histT[m]) * (1.0f + (float)PRES * occT[m]);
                if (pdir[n] >= 0 && pdir[n] != k) step += (float)TURN;
                float ng = g + step;
                if (gstamp[m] != searchId || ng < gcost[m]) {
                    gstamp[m] = searchId; gcost[m] = ng; parent[m] = n; pdir[m] = (int8_t)k; pq.push({ng + heur(xx, yy), m});
                }
            }
            // layer change
            bool freeVia = (fixedvia[c] == ni) || (ownViaStamp[c] == treeId);
            bool canVia = freeVia || ((hardV[c] == -1 || hardV[c] == ni) && !holeblock[c] && ownViaBlockStamp[c] != treeId);
            if (canVia) {
                float vc = freeVia ? 0.5f : (float)(VIA_BASE * (1.0 + histV[c]) + VIA_CONF * PRES * occV[c]);   // sharing a via spot costs like sharing ~VIA_CONF track cells
                if (HARD && !freeVia && occV[c]) canVia = false;
                if (!net.crit && !freeVia && frozenV[c]) canVia = false;
                if (net.crit && !freeVia) vc *= (float)CRIT_VIA;
                if (canVia && !freeVia) {                                 // the barrel must also be legal on every layer
                    bool ok = true; float extra = 0;
                    for (int l2 = 0; l2 < NL; l2++) { int m = l2 * N2 + c; if (hardT[m] != -1 && hardT[m] != ni) ok = false; }
                    if (!ok) canVia = false; else vc += extra;
                }
                if (canVia && net.kind && !freeVia && (net.kind == 1 || mask3v3[c])) {
                    float ng = g + vc;
                    if (gstamp[VGOAL] != searchId || ng < gcost[VGOAL]) { gstamp[VGOAL] = searchId; gcost[VGOAL] = ng; parent[VGOAL] = n; pq.push({ng, VGOAL}); }
                }
                if (canVia && !net.kind) for (int l2 = 0; l2 < NL; l2++) {
                    if (l2 == l) continue;
                    int m = l2 * N2 + c;
                    if (HARD && occT[m]) continue;
                    if (!net.crit && frozenT[m]) continue;
                    float ng = g + vc + (1.0f + histT[m]) * (1.0f + (float)PRES * occT[m]) - 1.0f;
                    if (gstamp[m] != searchId || ng < gcost[m]) {
                        gstamp[m] = searchId; gcost[m] = ng; parent[m] = n; pdir[m] = -1; pq.push({ng + heur(x, y), m});
                    }
                }
            }
        }
        if (goal < 0) { net.failed = true; return false; }
        vector<int> path; for (int n = (goal == VGOAL ? parent[VGOAL] : goal); n >= 0; n = parent[n]) path.push_back(n);
        reverse(path.begin(), path.end());
        if (goal == VGOAL) {                                             // the stub ends in a new via
            int c = nodeC(path.back()); ownViaStamp[c] = treeId; net.vias.push_back(c);
            for (int n : path) { if (treeStamp[n] != treeId) net.tcells.push_back(n); addTree(n); }
            path.push_back(-1 - c);                                      // marker: via at the end
            net.paths.push_back(path); left--; continue;
        }
        for (size_t i = 0; i < path.size(); i++) {
            int n = path[i];
            if (i > 0 && nodeL(path[i - 1]) != nodeL(n)) {
                int c = nodeC(n);
                if (fixedvia[c] != ni && ownViaStamp[c] != treeId) {
                    ownViaStamp[c] = treeId; net.vias.push_back(c);
                    int x = c / NY, y = c % NY;
                    for (auto& o : discVV) { int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue; if (o.dx || o.dy) ownViaBlockStamp[xx * NY + yy] = treeId; }
                }
            }
            if (treeStamp[n] != treeId) net.tcells.push_back(n);
            addTree(n);
        }
        if (path.size() > 1) net.paths.push_back(path);
        int t = tgtIdx[goal]; reached[t] = 1; left--;
        for (int n : net.terms[t]) addTree(n);
    }
    return true;
}

template <class T> static void readBin(const string& f, vector<T>& v, size_t n) {
    v.resize(n); FILE* fp = fopen(f.c_str(), "rb"); if (!fp) { fprintf(stderr, "cannot open %s\n", f.c_str()); exit(1); }
    size_t r = fread(v.data(), sizeof(T), n, fp); fclose(fp); if (r != n) { fprintf(stderr, "short read %s\n", f.c_str()); exit(1); }
}

int main(int argc, char** argv) {
    string dir = argc > 1 ? argv[1] : "build/nroute";
    int maxIter = argc > 2 ? atoi(argv[2]) : 60;
    if (getenv("VIA_BASE")) VIA_BASE = atof(getenv("VIA_BASE"));
    if (getenv("VIA_CONF")) VIA_CONF = atof(getenv("VIA_CONF"));
    double presInit = getenv("PRES0") ? atof(getenv("PRES0")) : 0.3, presMul = getenv("PRESMUL") ? atof(getenv("PRESMUL")) : 1.35;
    double presMax = getenv("PRESMAX") ? atof(getenv("PRESMAX")) : 50.0;
    bool wideStubs = !getenv("NOWIDE");
    int hardAt = getenv("HARDAT") ? atoi(getenv("HARDAT")) : 5;
    double histInc = getenv("HIST") ? atof(getenv("HIST")) : 0.25;
    int nn; { ifstream h(dir + "/header.txt"); h >> NX >> NY >> NL >> nn; }
    N2 = NX * NY; size_t NT = (size_t)NL * N2;
    // prep.py writes [layer][x][y] in C order, which is exactly node = l*N2 + x*NY + y
    readBin(dir + "/hardT.i16", hardT, NT); readBin(dir + "/hardV.i16", hardV, N2);
    readBin(dir + "/fixedvia.i16", fixedvia, N2); readBin(dir + "/holeblock.u8", holeblock, N2); readBin(dir + "/mask3v3.u8", mask3v3, N2);
    nets.resize(nn);
    { ifstream f(dir + "/nets.txt");
      for (int i = 0; i < nn; i++) { int nt; f >> nets[i].name >> nt >> nets[i].kind; nets[i].terms.resize(nt);
        for (int t = 0; t < nt; t++) { int nc; f >> nc; nets[i].terms[t].resize(nc);
          for (int k = 0; k < nc; k++) { int l, x, y; f >> l >> x >> y; nets[i].terms[t][k] = l * N2 + x * NY + y; } } } }
    occT.assign(NT, 0); occV.assign(N2, 0); histT.assign(NT, 0); histV.assign(N2, 0); markT.assign(NT, 0); markV.assign(N2, 0);
    gcost.assign(NT + 1, 0); gstamp.assign(NT + 1, 0); tgtStamp.assign(NT, 0); treeStamp.assign(NT, 0); parent.assign(NT + 1, -1); pdir.assign(NT, -1); tgtIdx.assign(NT, 0);
    ownViaStamp.assign(N2, 0); ownViaBlockStamp.assign(N2, 0);
    makeDisc(discTT, 14); makeDisc(discTV, getenv("TV2") ? atoi(getenv("TV2")) : 35); makeDisc(discVV, 64); makeDisc(discHist, 50); makeDisc(discTTw, 28); makeDisc(discTVw, getenv("TV2") ? atoi(getenv("TV2")) + 24 : 56); makeDisc(discWide, 5);
    frozenT.assign(NT, 0); frozenV.assign(N2, 0);
    // critical nets (env CRIT=name,name,...): negotiate among themselves on the empty board, with vias made
    // expensive, then freeze. They get the short, direct routes; the rest of the board works around them.
    vector<int> order, crit;
    { string cl = getenv("CRIT") ? getenv("CRIT") : ""; cl = "," + cl + ",";
      for (int i = 0; i < nn; i++) { if (nets[i].kind == 2 || (nets[i].kind == 1 && wideStubs)) nets[i].wide = true;      // +3V3 stubs always; GND stubs unless NOWIDE
        if (nets[i].kind == 2 || cl.find("," + nets[i].name + ",") != string::npos) { nets[i].crit = true; crit.push_back(i); } else order.push_back(i); } }
    if (!crit.empty()) {
        PRES = presInit; bool ok = false;
        for (int it = 0; it < 100 && !ok; it++) {
            int nfail = 0;
            for (int ni : crit) { if (it > 0) contribute(nets[ni], -1); if (!routeNet(ni)) nfail++; contribute(nets[ni], +1); }
            long conf = 0;
            for (int ni : crit) { for (int n : nets[ni].tcells) if (occT[n] >= 2) { conf++; histT[n] += (float)histInc; } for (int v : nets[ni].vias) if (occV[v] >= 2) { conf++; histV[v] += (float)histInc; } }
            ok = conf == 0 && nfail == 0; PRES = min(PRES * presMul, presMax);
        }
        if (!ok) { printf("critical nets did not converge\n"); return 3; }
        long wl = 0; int nv = 0;
        for (int ni : crit) { contribute(nets[ni], -1); wl += nets[ni].tcells.size(); nv += nets[ni].vias.size(); }
        for (int ni : crit) contribute(nets[ni], 0);
        printf("%d critical nets routed and frozen: %.0f mm, %d new vias\n", (int)crit.size(), wl * 0.05, nv);
        fill(histT.begin(), histT.end(), 0.0f); fill(histV.begin(), histV.end(), 0.0f);
    }
    PRES = presInit;
    int bestConf = 1 << 30;
    for (int it = 0; it < maxIter; it++) {
        int nfail = 0;
        for (int ni : order) {
            if (it > 0) contribute(nets[ni], -1);
            if (!routeNet(ni)) nfail++;
            contribute(nets[ni], +1);
        }
        // conflicts and history
        long conf = 0; int cnets = 0; long wl = 0; int nv = 0;
        vector<string> cn;
        for (auto& net : nets) {
            bool c = false; wl += net.tcells.size(); nv += net.vias.size();
            if (net.crit) continue;
            for (int n : net.tcells) if (occT[n] >= 2) {
                conf++; c = true;
                // remember the fight over the whole neighbourhood, or the two nets just shift their crossing by a cell
                int l = nodeL(n), cc = nodeC(n), x = cc / NY, y = cc % NY;
                for (auto& o : discHist) { int xx = x + o.dx, yy = y + o.dy; if (xx < 0 || yy < 0 || xx >= NX || yy >= NY) continue; histT[l * N2 + xx * NY + yy] += (float)(histInc / 8); }
                histT[n] += (float)histInc;
            }
            for (int v : net.vias) if (occV[v] >= 2) { conf++; c = true; histV[v] += (float)histInc; }
            if (c) { cnets++; cn.push_back(net.name); }
        }
        printf("iter %2d pres %8.2f  conflict cells %6ld  nets in conflict %3d  failed %d  length %.0f mm  vias %d\n", it, PRES, conf, cnets, nfail, wl * 0.05, nv);
        if (cnets > 0 && cnets <= 12) { printf("   "); for (auto& s : cn) printf(" %s", s.c_str()); printf("\n"); }
        for (auto& net : nets) if (net.failed) printf("   no path at all: %s\n", net.name.c_str());
        fflush(stdout);
        if (conf < bestConf || conf == 0) {
            bestConf = conf;
            ofstream o(dir + "/routes.txt");
            o << "CONFLICTS " << conf << "\n";
            { ofstream cf(dir + "/conflicts.txt");
              for (auto& net : nets) { for (int n : net.tcells) if (occT[n] >= 2) cf << net.name << " " << nodeL(n) << " " << nodeC(n) / NY << " " << nodeC(n) % NY << "\n";
                                       for (int v : net.vias) if (occV[v] >= 2) cf << net.name << " 9 " << v / NY << " " << v % NY << "\n"; } }
            for (auto& net : nets) {
                o << "NET " << net.name << " " << net.paths.size() << " " << (net.failed ? 1 : 0) << "\n";
                for (auto& p : net.paths) { o << "P " << p.size(); for (int n : p) { if (n < 0) { int c = -1 - n; o << " 9 " << c / NY << " " << c % NY; continue; } int c = nodeC(n); o << " " << nodeL(n) << " " << c / NY << " " << c % NY; } o << "\n"; }
            }
        }
        if (conf == 0 && nfail == 0) { printf("converged\n"); return 0; }
        if (cnets > 0 && cnets <= hardAt && nfail == 0) {
            // few nets left: re-route each of them with every other net treated as a fixed obstacle
            vector<int> bad;
            for (int i = 0; i < nn; i++) { if (nets[i].crit) continue; bool c = false; for (int n : nets[i].tcells) if (occT[n] >= 2) c = true; for (int v : nets[i].vias) if (occV[v] >= 2) c = true; if (c) bad.push_back(i); }
            sort(bad.begin(), bad.end());
            bool done = false; int tries = 0;
            do {
                vector<Net> save; for (int i : bad) save.push_back(nets[i]);
                HARD = true; bool ok = true;
                for (int i : bad) contribute(nets[i], -1);
                for (int i : bad) { nets[i].tcells.clear(); nets[i].vias.clear(); nets[i].paths.clear(); }
                vector<int> placed;
                for (int i : bad) { if (!routeNet(i)) { ok = false; break; } contribute(nets[i], +1); placed.push_back(i); }
                HARD = false;
                if (ok) { done = true; break; }
                for (int i : placed) contribute(nets[i], -1);
                for (size_t k = 0; k < bad.size(); k++) { nets[bad[k]] = save[k]; contribute(nets[bad[k]], +1); }
            } while (++tries < 720 && next_permutation(bad.begin(), bad.end()));
            if (done) {
                printf("finished the last %d nets in hard mode (order %d)\n", (int)bad.size(), tries);
                ofstream o(dir + "/routes.txt"); o << "CONFLICTS 0\n";
                for (auto& net : nets) {
                    o << "NET " << net.name << " " << net.paths.size() << " 0\n";
                    for (auto& p : net.paths) { o << "P " << p.size(); for (int n : p) { if (n < 0) { int c = -1 - n; o << " 9 " << c / NY << " " << c % NY; continue; } int c = nodeC(n); o << " " << nodeL(n) << " " << c / NY << " " << c % NY; } o << "\n"; }
                }
                printf("converged\n"); return 0;
            }
        }
        PRES = min(PRES * presMul, presMax);
    }
    printf("not converged; best had %d conflict cells\n", bestConf);
    return 2;
}
