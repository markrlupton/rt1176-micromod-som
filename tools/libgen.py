"""Generate the project library (KiCad 7 format):
  lib/rt1176-som.kicad_sym : MIMXRT1176DVMAB (6 units, from data/rt1176_balls.json), MicroMod_Card (edge connector)
  lib/rt1176-som.pretty/MicroMod_Card_Edge.kicad_mod : M.2 2222 Key-E card-edge fingers (SparkFun dimensions)
Run from anywhere: python3 tools/libgen.py"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DATA = os.path.join(HERE, 'data')
LIB = os.path.join(ROOT, 'lib'); os.makedirs(os.path.join(LIB, 'rt1176-som.pretty'), exist_ok=True)
balls = json.load(open(os.path.join(DATA, 'rt1176_balls.json')))
mmpins = {int(k): v for k, v in json.load(open(os.path.join(DATA, 'micromod_pins.json'))).items()}

def nat(s):
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', s)]

# ---------------------------------------------------------------- RT1176 symbol
UNITS = [  # (unit name, predicate on ball name)
    ('Power', lambda n: not n.startswith(('GPIO', 'MIPI', 'USB', 'XTAL', 'RTC_', 'CLK1', 'POR_B', 'ONOFF', 'TEST_MODE',
                                            'WAKEUP', 'PMIC', 'DAC_OUT'))),
    ('GPIO_AD', lambda n: n.startswith('GPIO_AD_')),
    ('LPSR / SNVS / system', lambda n: n.startswith(('GPIO_LPSR', 'GPIO_SNVS', 'USB', 'XTAL', 'RTC_', 'CLK1', 'POR_B',
                                                     'ONOFF', 'TEST_MODE', 'WAKEUP', 'PMIC', 'DAC_OUT'))),
    ('SD / DISP', lambda n: n.startswith(('GPIO_SD_', 'GPIO_DISP_'))),
    ('EMC', lambda n: n.startswith('GPIO_EMC_')),
    ('MIPI', lambda n: n.startswith('MIPI')),
]
POWER_IN = re.compile(r'^(VSS|DCDC_GND|DCDC_IN|DCDC_IN_Q|VDD_SOC_IN|VDD_LPSR_IN|VDD_SNVS_IN|NVCC_.*|VDDA_ADC_3P3|VDDA_ADC_1P8|'
                      r'VDD_USB_3P3|VDD_USB_1P8|VDDA_1P8_IN|ADC_VREFH|VDD_MIPI_1P0|VDD_MIPI_1P8)$')

def etype(n):
    if n.startswith('GPIO'): return 'bidirectional'
    if POWER_IN.match(n): return 'power_in'
    if n in ('POR_B', 'ONOFF', 'TEST_MODE', 'XTALI', 'RTC_XTALI', 'DCDC_PSWITCH', 'DCDC_MODE'): return 'input'
    if n in ('XTALO', 'RTC_XTALO', 'PMIC_ON_REQ', 'PMIC_STBY_REQ', 'DAC_OUT'): return 'output'
    return 'passive'     # regulator outputs, sense pins, DCDC_LP/LN, USB, MIPI, CLK1, WAKEUP

def fnt(sz=1.27): return f'(effects (font (size {sz} {sz})))'

def rt_symbol():
    out = []
    name = 'MIMXRT1176DVMAB'
    out.append(f'  (symbol "{name}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)')
    props = [('Reference', 'U', -17.78, 62.23, False), ('Value', name, 2.54, 62.23, False),
             ('Footprint', 'Package_BGA:MAPBGA_14x14mm_Layout17x17_P0.8mm', 0, -2.54, True),
             ('Datasheet', 'https://www.nxp.com/docs/en/data-sheet/IMXRT1170CEC.pdf', 0, -5.08, True),
             ('MPN', 'MIMXRT1176DVMAB', 0, -7.62, True)]
    for i, (k, v, x, y, hide) in enumerate(props):
        out.append(f'    (property "{k}" "{v}" (at {x} {y} 0) {"(effects (font (size 1.27 1.27)) hide)" if hide else fnt()})')
    used = set()
    for ui, (uname, pred) in enumerate(UNITS, start=1):
        pins = sorted([(n, b) for b, n in balls.items() if pred(n) and b not in used], key=lambda p: (nat(p[0]), nat(p[1])))
        used |= {b for n, b in pins}
        half = (len(pins) + 1) // 2
        left, right = pins[:half], pins[half:]
        w = 35.56; rows = max(len(left), len(right)); h = (rows + 1) * 2.54
        top = h / 2
        out.append(f'    (symbol "{name}_{ui}_1"')
        out.append(f'      (rectangle (start {-w/2} {top}) (end {w/2} {-top}) (stroke (width 0.254) (type default)) (fill (type background)))')
        out.append(f'      (text "{uname}" (at 0 {top + 1.27} 0) {fnt()})')
        for col, side in ((left, -1), (right, 1)):
            for i, (n, b) in enumerate(col):
                y = top - 2.54 * (i + 1)
                x = side * (w / 2 + 2.54); ang = 0 if side < 0 else 180
                out.append(f'      (pin {etype(n)} line (at {x:.2f} {y:.2f} {ang}) (length 2.54) (name "{n}" {fnt()}) (number "{b}" {fnt()}))')
        out.append('    )')
    assert len(used) == 289, len(used)
    out.append('  )')
    return '\n'.join(out)

# ---------------------------------------------------------------- MicroMod card-edge symbol
def mm_name(n):
    return re.sub(r'!([^!]+)!', r'~{\1}', n)

def mm_symbol():
    name = 'MicroMod_Card'
    out = [f'  (symbol "{name}" (pin_names (offset 1.016)) (in_bom no) (on_board yes)']
    for k, v, y, hide in (('Reference', 'J', 2.54, False), ('Value', name, 0, False),
                          ('Footprint', 'rt1176-som:MicroMod_Card_Edge', -2.54, True), ('Datasheet', '', -5.08, True)):
        out.append(f'    (property "{k}" "{v}" (at 0 {y} 0) {"(effects (font (size 1.27 1.27)) hide)" if hide else fnt()})')
    pins = sorted(mmpins)
    odd = [p for p in pins if p % 2]; even = [p for p in pins if not p % 2]
    rows = max(len(odd), len(even)); w = 25.4; h = (rows + 1) * 2.54; top = h / 2
    out.append(f'    (symbol "{name}_1_1"')
    out.append(f'      (rectangle (start {-w/2} {top}) (end {w/2} {-top}) (stroke (width 0.254) (type default)) (fill (type background)))')
    for col, side in ((odd, -1), (even, 1)):
        for i, p in enumerate(col):
            n = mmpins[p]; y = top - 2.54 * (i + 1)
            t = 'power_out' if n in ('3.3V',) else 'power_in' if n == 'GND' else 'passive'
            if n == 'GND': t = 'passive'
            x = side * (w / 2 + 2.54); ang = 0 if side < 0 else 180
            out.append(f'      (pin {t} line (at {x:.2f} {y:.2f} {ang}) (length 2.54) (name "{mm_name(n)}" {fnt()}) (number "{p}" {fnt()}))')
    out.append('    )')
    out.append('  )')
    return '\n'.join(out)

def write_symlib():
    s = '(kicad_symbol_lib (version 20220914) (generator rt1176_som_libgen)\n' + rt_symbol() + '\n' + mm_symbol() + '\n)\n'
    open(os.path.join(LIB, 'rt1176-som.kicad_sym'), 'w').write(s)

# ---------------------------------------------------------------- MicroMod edge footprint
def write_edge_fp():
    """Origin at the card edge, centred on the finger row (card x = 11 mm in SparkFun's frame).
    Card body is toward -Y. Odd pins on F.Cu (0.35 x 1.45 mm, centre 1.275 mm from the edge),
    even pins on B.Cu (0.35 x 1.95 mm, centre 1.525 mm). Pin n at X = 9.25 - 0.25*(n-1).
    Fingers have mask openings and no paste (gold fingers)."""
    L = ['(footprint "MicroMod_Card_Edge" (version 20221018) (generator rt1176_som_libgen) (layer "F.Cu")',
         '  (descr "MicroMod processor card edge, M.2 2222 Key E, 0.5 mm pitch per side (SparkFun MicroMod dimensions)")',
         '  (attr smd exclude_from_pos_files exclude_from_bom)',
         '  (fp_text reference "REF**" (at 0 -4.5) (layer "F.SilkS") hide (effects (font (size 0.8 0.8) (thickness 0.12))))',
         '  (fp_text value "MicroMod_Card_Edge" (at 0 -5.5) (layer "F.Fab") (effects (font (size 0.8 0.8) (thickness 0.12))))']
    for p in sorted(mmpins):
        x = 9.25 - 0.25 * (p - 1)
        if p % 2:
            L.append(f'  (pad "{p}" smd rect (at {x:.3f} -1.275) (size 0.35 1.45) (layers "F.Cu" "F.Mask"))')
        else:
            L.append(f'  (pad "{p}" smd rect (at {x:.3f} -1.525) (size 0.35 1.95) (layers "B.Cu" "B.Mask"))')
    # courtyard around the finger area on both sides
    for lay in ('F.CrtYd', 'B.CrtYd'):
        L.append(f'  (fp_rect (start -9.925 -3.6) (end 9.925 0) (stroke (width 0.05) (type default)) (fill none) (layer "{lay}"))')
    L.append(')')
    open(os.path.join(LIB, 'rt1176-som.pretty', 'MicroMod_Card_Edge.kicad_mod'), 'w').write('\n'.join(L) + '\n')

if __name__ == '__main__':
    write_symlib(); write_edge_fp()
    print('wrote lib/rt1176-som.kicad_sym and lib/rt1176-som.pretty/MicroMod_Card_Edge.kicad_mod')
