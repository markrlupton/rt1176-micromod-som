"""Choose RT1176 pads for every MicroMod signal so routes from ball to finger stay short.

Geometry (card frame, top view, mm): fingers along y = 0, pin n at x = 20.25 - 0.25*(n-1) (pin 1 at the right).
U1 centred at (11, 11.9), rotated so that, seen from the top, A1 is at the top-right corner:
row A..U runs right -> left (x = 11 + (8 - row_index)*0.8), column 17 faces the fingers
(depth from the BGA's finger-side edge = (17 - column)*0.8 mm). This is the standard top-view
ball map rotated 90 degrees clockwise (KiCad footprint rotation -90).

Cost of putting a signal on a pad = horizontal offset to its finger + 0.6 x depth. Peripheral groups
(I2C, UART, SPI, CAN, SAI4) are searched over every instance and pad option; single-pad signals
(GPIO / PWM / ADC) are then placed with the Hungarian algorithm on the pads left over.
Writes data/optimized.json; pinmap.py is then updated from it by hand-checked edit."""
import itertools, json, os, re, sys
import numpy as np
from scipy.optimize import linear_sum_assignment

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, 'data')
mux = json.load(open(os.path.join(DATA, 'mux.json')))
balls = json.load(open(os.path.join(DATA, 'rt1176_balls.json')))
pad2ball = {v: k for k, v in balls.items() if v.startswith('GPIO')}
ROWS = 'ABCDEFGHJKLMNPRTU'

def pad_xy(pad):
    b = pad2ball[pad]; ri = ROWS.index(b[0]); c = int(b[1:])
    return 11 + (8 - ri) * 0.8, (17 - c) * 0.8
def finger_x(pin): return 20.25 - 0.25 * (pin - 1)
def cost(pin, pad):
    x, d = pad_xy(pad); return abs(finger_x(pin) - x) + 0.6 * d

RESERVED = set(
    [f'GPIO_SD_B2_{i:02d}' for i in range(12)]                       # flash bank
    + [f'GPIO_DISP_B1_{i:02d}' for i in range(6, 12)]                 # BOOT_CFG straps
    + [f'GPIO_DISP_B2_{i:02d}' for i in range(6)]
    + ['GPIO_LPSR_02', 'GPIO_LPSR_03',                                # BOOT_MODE
       'GPIO_LPSR_14', 'GPIO_LPSR_15',                                # SWD (test pads)
       'GPIO_LPSR_08',                                                # status LED
       'GPIO_LPSR_05']                                                # SAI4_MCLK test pad
    + [f'GPIO_SNVS_{i:02d}' for i in range(10)]                       # 1.75 V domain
    + [f'GPIO_SD_B1_{i:02d}' for i in range(6)]                       # USDHC1 (SDIO, fixed)
    + ['GPIO_AD_17', 'GPIO_AD_20', 'GPIO_AD_21', 'GPIO_AD_22', 'GPIO_AD_23'])   # SAI1 (fixed)
USABLE = [p for p in pad2ball if p not in RESERVED and p in mux]

def pads_with(fn):
    return [p for p in USABLE if fn in mux[p]]

# peripheral groups: name -> list of candidate {pin: function} maps (one per instance)
def inst_options(pattern_funcs):
    """pattern_funcs: {pin: 'LPI2C{n}_SDA'} with {n} placeholder; tries every instance number."""
    out = []
    for n in list(range(1, 13)):
        fm = {pin: f.format(n=n) for pin, f in pattern_funcs.items()}
        if all(pads_with(f) for f in fm.values()): out.append((n, fm))
    return out

GROUPS = {
    'I2C':  inst_options({12: 'LPI2C{n}_SDA', 14: 'LPI2C{n}_SCL'}),
    'I2C1': inst_options({51: 'LPI2C{n}_SDA', 53: 'LPI2C{n}_SCL'}),
    'UART1': inst_options({17: 'LPUART{n}_TX', 19: 'LPUART{n}_RX'}),
    'UART2': inst_options({22: 'LPUART{n}_TX', 20: 'LPUART{n}_RX'}),
    'SPI':  inst_options({57: 'LPSPI{n}_SCK', 55: 'LPSPI{n}_PCS0', 59: 'LPSPI{n}_SDO', 61: 'LPSPI{n}_SDI'}),
    'CAN':  inst_options({43: 'CAN{n}_TX', 41: 'CAN{n}_RX'}),
    'SAI4': [(4, {13: 'SAI4_TX_SYNC', 15: 'SAI4_TX_DATA', 21: 'SAI4_RX_DATA', 23: 'SAI4_TX_BCLK'})],
}
EXCLUSIVE = [('I2C', 'I2C1'), ('UART1', 'UART2')]   # must be different instances

def configs(group, keep=40):
    res = []
    for n, fm in GROUPS[group]:
        pins = list(fm)
        for combo in itertools.product(*[pads_with(fm[p]) for p in pins]):
            if len(set(combo)) < len(combo): continue
            c = sum(cost(p, pad) for p, pad in zip(pins, combo))
            res.append((c, n, dict(zip(pins, combo)), fm))
    res.sort(key=lambda r: r[0]); return res[:keep]

SINGLES = {   # pin: required function regex (None = any GPIO)
    32: r'FLEXPWM', 47: r'FLEXPWM', 10: r'FLEXPWM', 18: r'FLEXPWM',
    34: r'ADC', 38: r'ADC', 49: r'ADC', 67: r'ADC', 8: r'ADC',
    40: None, 42: None, 44: None, 46: None, 48: None, 73: None, 71: None, 69: None, 65: None, 63: None,
    16: None, 4: None}

def place_singles(free):
    pins = list(SINGLES); pads = sorted(free)
    big = 1e6; C = np.full((len(pins), len(pads)), big)
    for i, pin in enumerate(pins):
        for j, pad in enumerate(pads):
            rx = SINGLES[pin]
            if rx is None or any(re.match(rx, f) for f in mux[pad]): C[i, j] = cost(pin, pad)
    r, c = linear_sum_assignment(C)
    if C[r, c].max() >= big: return None, big
    return {pins[i]: pads[j] for i, j in zip(r, c)}, C[r, c].sum()

BEAM = int(os.environ.get("BEAM", "4"))
def search():
    order = ['SAI4', 'SPI', 'UART1', 'UART2', 'I2C', 'I2C1', 'CAN']
    cand = {g: configs(g) for g in order}
    best = (1e9, None)
    def rec(i, used, chosen, total):
        nonlocal best
        if total >= best[0]: return
        if i == len(order):
            sing, sc = place_singles([p for p in USABLE if p not in used])
            if sing is not None and total + sc < best[0]: best = (total + sc, (dict(chosen), sing))
            return
        g = order[i]
        for c, n, pinpad, fm in cand[g][:BEAM]:
            if set(pinpad.values()) & used: continue
            if any(g in pair and chosen.get(pair[0] if pair[1] == g else pair[1], (None,))[0] == n for pair in EXCLUSIVE): continue
            chosen[g] = (n, pinpad, fm)
            rec(i + 1, used | set(pinpad.values()), chosen, total + c)
            del chosen[g]
    rec(0, set(), {}, 0.0)
    return best

if __name__ == '__main__':
    total, (groups, singles) = search()
    out = {'cost': total, 'groups': {}, 'singles': {}}
    for g, (n, pinpad, fm) in groups.items():
        out['groups'][g] = {str(p): [pad, fm[p]] for p, pad in pinpad.items()}
    for pin, pad in singles.items():
        rx = SINGLES[pin]; fn = next((f for f in mux[pad] if rx and re.match(rx, f)), 'GPIO')
        out['singles'][str(pin)] = [pad, fn]
    json.dump(out, open(os.path.join(DATA, 'optimized.json'), 'w'), indent=1)
    print('total cost %.1f' % total)
    for g, v in out['groups'].items():
        print(g, {p: (pad.replace('GPIO_', ''), f, round(cost(int(p), pad), 1)) for p, (pad, f) in v.items()})
    for p, (pad, f) in sorted(out['singles'].items(), key=lambda x: int(x[0])):
        print(' ', p, pad.replace('GPIO_', ''), f, round(cost(int(p), pad), 1))
