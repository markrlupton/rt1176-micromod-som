import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); DATA=os.path.join(HERE,'data'); sys.path.insert(0,HERE)
"""Render the stage-1 floorplan of the RT1176 MicroMod card (top view) as SVG/PNG.
Card frame: SparkFun/Eagle coordinates, x 0..22 mm, y 0 at the finger edge, up to 22 mm. Drawn with y flipped."""
import json, math, sys
sys.path.insert(0, '.')
from pinmap import PINMAP, INTERNAL

S = 34                      # px per mm
M = 1.2                     # margin mm (left)
W_MM, H_MM = 22 + 2 * M + 15.5, 22 + 2 * M + 2.5
def X(x): return (x + M) * S
def Y(y): return (22 + M + 1.2 - y) * S

balls = list(json.load(open(os.path.join(DATA,'mcu_maps.json')))['ours'].values())[0]
rows = 'ABCDEFGHJKLMNPRTU'
BGA_CX, BGA_CY = 11.0, 11.9          # BGA centre (card frame)
# Orientation: the standard top-view ball map (A1 top-left, A1..A17 along the top edge) rotated
# 90 degrees clockwise, so A1 is at the top-right, column 17 faces the fingers and row A is on the right.
def ball_xy(b):
    ri = rows.index(b[0]); c = int(b[1:])
    return BGA_CX - (ri - 8) * 0.8, BGA_CY - (c - 9) * 0.8

GROUP = {  # colour by function
    'USB': '#7b3fe4', 'SAI1': '#e4572e', 'SAI4': '#ff9f80', 'LPSPI': '#2e86ab', 'USDHC1': '#17a398', 'LPUART': '#f2a541',
    'LPI2C': '#c33c54', 'CAN': '#3f7d20', 'ADC': '#a1662f', 'PWM': '#d97ab6', 'GPIO': '#6c757d',
    'SWD/BOOT/RST': '#111111', 'FLASH': '#0b3d91', 'STRAP': '#9aa5b1', 'XTAL/SNVS': '#b08900'}
def group_of(fn, pad):
    for k, g in [('USB', 'USB'), ('SAI4', 'SAI4'), ('SAI', 'SAI1'), ('LPSPI', 'LPSPI'), ('USDHC1', 'USDHC1'), ('LPUART', 'LPUART'),
                 ('LPI2C', 'LPI2C'), ('CAN', 'CAN'), ('ADC', 'ADC'), ('FLEXPWM', 'PWM'), ('SWD', 'SWD/BOOT/RST'),
                 ('BOOT', 'SWD/BOOT/RST'), ('reset', 'SWD/BOOT/RST')]:
        if k in fn: return g
    return 'GPIO'
use = {}
for pin, (nm, tp, pad, fn, note) in PINMAP.items():
    if pad.startswith('GPIO') or pad.startswith('USB') or pad in ('POR_B', 'VDD_SNVS_IN'):
        use[pad] = (group_of(fn, pad), pin)
for pad, txt in INTERNAL.items():
    use[pad] = ('FLASH' if 'FLEXSPI' in txt else 'STRAP' if 'BOOT' in txt else 'GPIO', None)
use['POR_B'] = ('SWD/BOOT/RST', 6)
for p in ('XTALI', 'XTALO', 'RTC_XTALI', 'RTC_XTALO'): use[p] = ('XTAL/SNVS', None)

o = []
o.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W_MM*S:.0f}" height="{H_MM*S:.0f}" font-family="Helvetica,Arial" >')
o.append(f'<rect width="100%" height="100%" fill="white"/>')
# outline: finger tab + body + key notch + screw notch
def P(x, y): return f'{X(x):.1f},{Y(y):.1f}'
o.append(f'<path d="M {P(1.075,0)} L {P(13.025,0)} L {P(13.025,2.29)} A {0.6*S} {0.6*S} 0 0 0 {P(14.225,2.29)} L {P(14.225,0)} L {P(20.925,0)} '
         f'L {P(20.925,3.49)} L {P(22,4.59)} L {P(22,20.99)} A {S} {S} 0 0 0 {P(21,21.99)} L {P(16.75,21.99)} '
         f'A {1.75*S} {1.75*S} 0 0 1 {P(13.25,21.99)} L {P(1,21.99)} A {S} {S} 0 0 0 {P(0,20.99)} L {P(0,4.59)} L {P(1.075,3.49)} Z" '
         f'fill="#e9f5e9" stroke="#2d6a2d" stroke-width="2"/>')
# screw keepout
o.append(f'<circle cx="{X(15)}" cy="{Y(21.99)}" r="{2.5*S}" fill="none" stroke="#999" stroke-dasharray="6,4"/>')
o.append(f'<text x="{X(15)}" y="{Y(22.6)}" font-size="11" text-anchor="middle" fill="#666">M2.5 screw slot + head keep-out</text>')
# fingers (odd pins top side), colour by group
for pin in range(1, 76, 2):
    x = 11 + 9.25 - (pin - 1) * 0.25
    e = PINMAP.get(pin); g = group_of(e[3], e[2]) if e and e[2].startswith(('GPIO', 'USB', 'SUP', 'VDD')) else None
    col = GROUP.get(g, '#d4af37') if e and e[0] not in ('GND', '3.3V') else ('#d4af37' if e else '#eee')
    o.append(f'<rect x="{X(x-0.175):.1f}" y="{Y(2.0):.1f}" width="{0.35*S:.1f}" height="{1.45*S:.1f}" fill="{col}"/>')
    if pin in (1, 11, 21, 31, 41, 51, 61, 71, 75):
        o.append(f'<text x="{X(x)}" y="{Y(-0.55)}" font-size="10" text-anchor="middle">{pin}</text>')
# zones: BGA top-side keepout and bands
o.append(f'<rect x="{X(4)}" y="{Y(18.9)}" width="{14*S}" height="{14*S}" fill="#f7f7f7" stroke="#333" stroke-width="1.5"/>')
for b, names in balls.items():
    x, y = ball_xy(b); n = names[0]
    g = None
    for nn in names:
        if nn in use: g = use[nn][0]
    if n.startswith(('VSS', 'DCDC_GND')): col, r = '#cfcfcf', 0.14
    elif g: col, r = GROUP[g], 0.26
    elif not n.startswith('GPIO') and not n.startswith('MIPI'): col, r = '#f4c2c2', 0.2     # power / analog
    else: col, r = '#ffffff', 0.17
    o.append(f'<circle cx="{X(x):.1f}" cy="{Y(y):.1f}" r="{r*S:.1f}" fill="{col}" stroke="#888" stroke-width="0.5"/>')
o.append(f'<text x="{X(4)+3}" y="{Y(18.9)-4}" font-size="10">U1 RT1176 (MIMXRT1176DVMAB) 14×14 BGA, A1 top-right (90° CW), column 17 toward fingers</text>')
# top-side parts (approximate)
def part(x, y, w, h, label, col='#fff3bf', fs=9, rot=False):
    o.append(f'<rect x="{X(x):.1f}" y="{Y(y+h):.1f}" width="{w*S:.1f}" height="{h*S:.1f}" fill="{col}" stroke="#555"/>')
    tx, ty = X(x + w / 2), Y(y + h / 2) + 3
    tr = f' transform="rotate(-90 {tx:.1f} {ty-3:.1f})"' if rot else ''
    o.append(f'<text x="{tx:.1f}" y="{ty:.1f}" font-size="{fs}" text-anchor="middle"{tr}>{label}</text>')
part(0.6, 4.7, 3.0, 2.0, '24 MHz', '#fff0b3')
part(0.6, 7.2, 3.0, 1.9, '32.768k', '#fff0b3')
part(0.6, 9.6, 3.0, 3.0, 'Reset sup.', '#e6e6e6')
part(0.6, 13.0, 3.0, 2.6, 'BAT54C', '#e6e6e6')
part(0.2, 16.4, 4.0, 4.0, '4.7µH 4×4', '#ffd6a5')
part(4.7, 19.25, 7.6, 2.2, 'bulk 0805s (DCDC_IN, DCDC_ANA)', '#ffe0e0')
part(18.5, 4.7, 3.0, 5.5, 'Flash (see notes)', '#cfe0ff', rot=True)
part(18.5, 10.7, 3.0, 5.4, 'BOOT_CFG pulls', '#eeeeee', rot=True)
part(18.5, 16.6, 3.0, 2.4, 'inverter', '#e6e6e6')
part(18.7, 20.0, 1.6, 0.9, 'LED', '#d0f0c0', fs=7)
# legend
lx = 24.2
o.append(f'<text x="{X(lx)}" y="{Y(21.7)}" font-size="13" font-weight="bold">RT1176 MicroMod card: floorplan v1 (top view)</text>')
yy = 20.6
for g, c in GROUP.items():
    o.append(f'<circle cx="{X(lx)+6}" cy="{Y(yy)-4}" r="6" fill="{c}"/><text x="{X(lx)+18}" y="{Y(yy)}" font-size="12">{g}</text>')
    yy -= 0.78
notes = ['22 × 22 mm MicroMod outline, 0.8 mm 6-layer, ENIG + bevelled fingers',
         'Bottom side: 0402 decoupling under the BGA, 3 × 22 µF 0805 on the core rail',
         'Everything else 0603/0805. Tight fits: 4×4 inductor (top-left)',
         'and the 6×5 mm flash (right band is 3.7 mm wide)',
         'Grey balls = ground, pink = power/analog, white = unused',
         'Fingers drawn: odd pins (top side); even pins are on the bottom side',
         'USB OTG1 balls sit right above pins 3/5']
for t in notes:
    yy -= 0.15; o.append(f'<text x="{X(lx)}" y="{Y(yy)}" font-size="11" fill="#333">{t}</text>'); yy -= 0.7
o.append('</svg>')
open(os.path.join(ROOT,'docs','floorplan_v1.svg'), 'w').write('\n'.join(o))
print('ok')
