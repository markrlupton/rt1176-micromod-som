"""Generate the KiCad 7 schematic for the RT1176 MicroMod SOM from one parts/nets table.

  python3 tools/schgen.py   -> rt1176-micromod-som.kicad_sch (root) + sheets/*.kicad_sch

Connectivity is by global labels: every connected pin gets a short wire and a global label carrying its
net name; every unused pin gets a no-connect flag. The pin map comes from tools/pinmap.py.
"""
import json, math, os, re, sys, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DATA = os.path.join(HERE, 'data')
sys.path.insert(0, HERE)
from pinmap import PINMAP, INTERNAL

PROJECT = 'rt1176-micromod-som'
KLIB = '/usr/share/kicad/symbols'
NS = uuid.UUID('6f1c1c2e-5a3b-4f43-9b7e-1176a0c0ffee')
def U(*k): return str(uuid.uuid5(NS, '/'.join(map(str, k))))
REV = 'A'
TITLE = 'RT1176 MicroMod SOM'

# --------------------------------------------------------------------------- nets for the MicroMod card edge
def sig(name):
    m = {'USB_D+': 'USB_DP', 'USB_D-': 'USB_DN', 'USBHOST_D+': 'USBHOST_DP', 'USBHOST_D-': 'USBHOST_DN',
         'RESET#': 'RESET_N', 'BOOT#': 'BOOT_N', 'I2C_INT#': 'I2C_INT_N', 'SPI_CS#': 'SPI_CS_N',
         'BATT_VIN/3': 'BATT_VIN3', '3.3V': '+3V3', '3.3V_EN': 'V3V3_EN'}
    return m.get(name, name)
EDGE_NET = {}
for pin, (nm, tp, pad, fn, note) in PINMAP.items():
    n = sig(nm)
    if pin in (13, 15, 21, 23):
        n = {13: 'AUD2_LRCLK', 15: 'AUD2_OUT', 21: 'AUD2_IN', 23: 'AUD2_BCLK'}[pin]
    EDGE_NET[pin] = n

balls = json.load(open(os.path.join(DATA, 'rt1176_balls.json')))
name2balls = {}
for b, n in balls.items(): name2balls.setdefault(n, []).append(b)

# RT1176 ball -> net
U1 = {}
for pin, (nm, tp, pad, fn, note) in PINMAP.items():
    if pad.startswith('GPIO_'):
        for b in name2balls[pad]: U1[b] = EDGE_NET[pin]
SPECIAL = {'USB1_DP': 'USB_DP', 'USB1_DN': 'USB_DN', 'USB1_VBUS': 'USB_VIN', 'USB2_DP': 'USBHOST_DP', 'USB2_DN': 'USBHOST_DN',
           'POR_B': 'POR_B', 'XTALI': 'XTALI', 'XTALO': 'XTALO', 'RTC_XTALI': 'RTC_XTALI', 'RTC_XTALO': 'RTC_XTALO'}
INTERNAL_NET = {'GPIO_SD_B2_06': 'FLASH_CS_N', 'GPIO_SD_B2_07': 'FLASH_CLK', 'GPIO_SD_B2_08': 'FLASH_IO0',
                'GPIO_SD_B2_09': 'FLASH_IO1', 'GPIO_SD_B2_10': 'FLASH_IO2', 'GPIO_SD_B2_11': 'FLASH_IO3',
                'GPIO_LPSR_02': 'BOOT_MODE0', 'GPIO_LPSR_08': 'LED', 'GPIO_LPSR_14': 'SWCLK', 'GPIO_LPSR_15': 'SWDIO',
                'GPIO_LPSR_05': 'SAI4_MCLK'}
BOOT_CFG_PADS = [f'GPIO_DISP_B1_{i:02d}' for i in range(6, 12)] + [f'GPIO_DISP_B2_{i:02d}' for i in range(6)]
for i, p in enumerate(BOOT_CFG_PADS): INTERNAL_NET[p] = f'BOOT_CFG{i}'
PWR = {}
for n in name2balls:
    if n in ('VSS', 'DCDC_GND', 'TEST_MODE'): PWR[n] = 'GND'
    elif n in ('DCDC_IN', 'DCDC_IN_Q', 'VDD_LPSR_IN', 'VDD_USB_3P3') or (n.startswith('NVCC_') and n != 'NVCC_SNVS'): PWR[n] = '+3V3'
    elif n in ('DCDC_DIG', 'DCDC_DIG_SENSE', 'VDD_SOC_IN'): PWR[n] = 'DCDC_DIG'
    elif n in ('DCDC_ANA', 'DCDC_ANA_SENSE', 'VDDA_1P8_IN', 'VDDA_ADC_1P8', 'VDD_USB_1P8'): PWR[n] = 'DCDC_ANA'
    elif n in ('VDD_SNVS_ANA', 'NVCC_SNVS'): PWR[n] = 'VDD_SNVS_ANA'
    elif n in ('ADC_VREFH', 'VDDA_ADC_3P3', 'DCDC_LP', 'DCDC_LN', 'DCDC_PSWITCH', 'DCDC_MODE', 'VDD_LPSR_ANA', 'VDD_LPSR_DIG',
               'VDDA_1P0', 'VDD_SNVS_DIG', 'VDD_SNVS_IN', 'VDD_MIPI_1P0', 'VDD_MIPI_1P8'): PWR[n] = n
for b, n in balls.items():
    if b in U1: continue
    if n in SPECIAL: U1[b] = SPECIAL[n]
    elif n in INTERNAL_NET: U1[b] = INTERNAL_NET[n]
    elif n in PWR: U1[b] = PWR[n]
    elif n == 'GPIO_LPSR_03': U1[b] = 'BOOT_N'          # BOOT_MODE1 = BOOT# directly
    else: U1[b] = None                                 # no-connect

# --------------------------------------------------------------------------- parts
FP = {'0402': 'Capacitor_SMD:C_0402_1005Metric', '0603': 'Capacitor_SMD:C_0603_1608Metric', '0805': 'Capacitor_SMD:C_0805_2012Metric',
      'R0603': 'Resistor_SMD:R_0603_1608Metric', 'R0402': 'Resistor_SMD:R_0402_1005Metric'}
parts = []    # dict(ref, lib, value, fp, sheet, unit, pins{num:net}, fields{}, pos)
def part(ref, lib, value, fp, sheet, pins, unit=1, **fields):
    parts.append(dict(ref=ref, lib=lib, value=value, fp=fp, sheet=sheet, unit=unit, pins=pins, fields=fields))

counters = {}
def nref(p):
    counters[p] = counters.get(p, 0) + 1; return f'{p}{counters[p]}'
def cap(net, value, size, sheet, note=''):
    part(nref('C'), 'Device:C_Small', value, FP[size], sheet, {'1': net, '2': 'GND'}, Note=note)
def res(a, b, value, sheet, size='R0603', note=''):
    part(nref('R'), 'Device:R_Small', value, FP[size], sheet, {'1': a, '2': b}, Note=note)

# MicroMod edge (sheet edge)
mmpins = {int(k): v for k, v in json.load(open(os.path.join(DATA, 'micromod_pins.json'))).items()}
jp = {}
for p, nm in mmpins.items():
    if nm == 'GND': jp[str(p)] = 'GND'
    elif nm == '3.3V': jp[str(p)] = '+3V3'
    elif p in EDGE_NET: jp[str(p)] = EDGE_NET[p]
    else: jp[str(p)] = None
part('J1', 'rt1176-som:MicroMod_Card', 'MicroMod_Card', 'rt1176-som:MicroMod_Card_Edge', 'edge', jp)
cap('+3V3', '22uF', '0805', 'edge', '3.3 V input bulk, at pins 2/74')
cap('+3V3', '10uF', '0805', 'edge', '3.3 V input bulk')
cap('USB_VIN', '100nF', '0603', 'edge', 'USB1_VBUS sense')
# reset supervisor: monitors 3.3 V, MicroMod RESET# on MR, open-drain RESET to POR_B (internal 100k pull-up in SNVS domain)
part('U2', 'Power_Supervisor:TPS3808DBV', 'TPS3808G30DBVR', 'Package_TO_SOT_SMD:SOT-23-6', 'edge',
     {'1': 'POR_B', '2': 'GND', '3': 'RESET_N', '4': None, '5': '+3V3', '6': '+3V3'}, LCSC='C189211', MPN='TPS3808G30DBVR')
cap('+3V3', '100nF', '0603', 'edge', 'U2 bypass')
# boot: BOOT# -> BOOT_MODE1 directly, inverted -> BOOT_MODE0
part('U3', '74xGxx:74LVC1G04', 'SN74LVC1G04DBVR', 'Package_TO_SOT_SMD:SOT-23-5', 'edge',
     {'2': 'BOOT_N', '3': 'GND', '4': 'BOOT_MODE0', '5': '+3V3'}, LCSC='C7827', MPN='SN74LVC1G04DBVR')
cap('+3V3', '100nF', '0603', 'edge', 'U3 bypass')
res('+3V3', 'BOOT_N', '10k', 'edge', note='BOOT# pull-up: released = internal boot (BOOT_MODE 10)')
# test pads (bottom side, pogo-pin fixture)
for i, (net, txt) in enumerate([('SWDIO', 'SWDIO'), ('SWCLK', 'SWCLK'), ('RESET_N', 'RESET#'), ('BOOT_N', 'BOOT#'),
                                ('+3V3', '3V3'), ('GND', 'GND'), ('SAI4_MCLK', 'SAI4_MCLK')], start=1):
    part(f'TP{i}', 'Connector:TestPoint', txt, 'TestPoint:TestPoint_Pad_D1.0mm', 'edge', {'1': net})

# MCU I/O units on sheet mcu
for unit in (2, 3, 4, 5, 6):
    part('U1', 'rt1176-som:MIMXRT1176DVMAB', 'MIMXRT1176DVMAB', 'Package_BGA:MAPBGA_14x14mm_Layout17x17_P0.8mm',
         'mcu', None, unit=unit, MPN='MIMXRT1176DVMAB')
part('U1', 'rt1176-som:MIMXRT1176DVMAB', 'MIMXRT1176DVMAB', 'Package_BGA:MAPBGA_14x14mm_Layout17x17_P0.8mm',
     'power', None, unit=1, MPN='MIMXRT1176DVMAB')

# power sheet
part('L1', 'Device:L_Small', '4.7uH', 'Inductor_SMD:L_Changjiang_FNR4030S', 'power', {'1': 'DCDC_LN', '2': 'DCDC_LP'},
     LCSC='C57269', MPN='SWPA4030S4R7MT', Note='NXP: 4.7 uH, Isat > 1.5 A, DCR < 0.1 ohm. Footprint: verify against Sunlord SWPA4030 land pattern')
part('D1', 'Diode:BAT54C', 'BAT54C', 'Package_TO_SOT_SMD:SOT-23', 'power', {'1': '+3V3', '2': 'RTC_3V', '3': 'VDD_SNVS_IN'},
     LCSC='C37704', MPN='BAT54C,215', Note='diode-OR: 3.3 V and MicroMod RTC_3V (pin 72) -> VDD_SNVS_IN')
part('FB1', 'Device:FerriteBead_Small', '120R@100MHz', 'Inductor_SMD:L_0603_1608Metric', 'power', {'1': 'DCDC_ANA', '2': 'ADC_VREFH'},
     Note='ADC reference from DCDC_ANA (1.8 V): ADC full scale is 1.8 V')
part('FB2', 'Device:FerriteBead_Small', '120R@100MHz', 'Inductor_SMD:L_0603_1608Metric', 'power', {'1': '+3V3', '2': 'VDDA_ADC_3P3'})
res('+3V3', 'DCDC_PSWITCH', '10k', 'power', note='PSWITCH RC: 10 ms, NXP window 5-40 ms')
cap('DCDC_PSWITCH', '1uF', '0603', 'power', 'PSWITCH RC')
res('DCDC_MODE', 'GND', '10k', 'power')
res('VDD_MIPI_1P0', 'GND', '10k', 'power', note='MIPI unused: supply via 10k to GND (NXP HDG)')
res('VDD_MIPI_1P8', 'GND', '10k', 'power', note='MIPI unused: supply via 10k to GND (NXP HDG)')
for v, s in (('22uF', '0805'), ('4.7uF', '0603'), ('100nF', '0402'), ('100nF', '0402')): cap('+3V3', v, s, 'power', 'DCDC_IN')
for v, s in (('22uF', '0805'), ('22uF', '0805'), ('22uF', '0805'), ('2.2uF', '0402'), ('2.2uF', '0402'), ('1uF', '0402'),
             ('1uF', '0402'), ('100nF', '0402'), ('100nF', '0402'), ('100nF', '0402')):
    cap('DCDC_DIG', v, s, 'power', 'DCDC_DIG / VDD_SOC_IN: ~71 uF total (NXP ~66 uF)')
for v, s, n in (('10uF', '0603', 'DCDC_ANA'), ('2.2uF', '0402', 'DCDC_ANA'), ('1uF', '0402', 'VDDA_1P8_IN, under M11'),
                ('1uF', '0402', 'VDDA_ADC_1P8, under K15'), ('100nF', '0402', 'VDD_USB_1P8, under H12')):
    cap('DCDC_ANA', v, s, 'power', n)
for net, v, n in (('ADC_VREFH', '1uF', 'under G16'), ('ADC_VREFH', '100nF', ''), ('VDDA_ADC_3P3', '1uF', 'under J13'),
                  ('VDDA_ADC_3P3', '100nF', ''), ('+3V3', '2.2uF', 'VDD_LPSR_IN, under R12'), ('VDD_LPSR_ANA', '4.7uF', 'under P12'),
                  ('VDD_LPSR_DIG', '2.2uF', 'under P11'), ('VDDA_1P0', '2.2uF', 'under N11'), ('VDD_SNVS_IN', '1uF', 'under U12'),
                  ('VDD_SNVS_ANA', '2.2uF', 'under U14'), ('VDD_SNVS_ANA', '100nF', 'NVCC_SNVS, under U11'),
                  ('VDD_SNVS_DIG', '220nF', 'under T14')):
    cap(net, v, '0402', 'power', n)
for n in ('NVCC_EMC1', 'NVCC_EMC1', 'NVCC_EMC2', 'NVCC_GPIO', 'NVCC_SD1', 'NVCC_SD2', 'NVCC_DISP1', 'NVCC_DISP2', 'NVCC_LPSR'):
    cap('+3V3', '2.2uF', '0402', 'power', n)
cap('+3V3', '100nF', '0402', 'power', 'NVCC_EMC1'); cap('+3V3', '100nF', '0402', 'power', 'NVCC_EMC2')
cap('+3V3', '1uF', '0402', 'power', 'VDD_USB_3P3, under G12')

# memory / clocks sheet
part('U4', 'Memory_Flash:W25Q32JVSS', 'GD25Q128EQIGR', 'rt1176-som:USON-8-1EP_4x4mm_P0.8mm_EP2.3x3mm_GigaDevice', 'mem',
     {'1': 'FLASH_CS_N', '2': 'FLASH_IO1', '3': 'FLASH_IO2', '4': 'GND', '5': 'FLASH_IO0', '6': 'FLASH_CLK', '7': 'FLASH_IO3', '8': '+3V3'},
     MPN='GD25Q128EQIGR', Note='16 MB QSPI NOR, USON-8 4x4 (footprint from DS-00480 rev 1.4; EP to GND). QE defaults to 0: WP#/HOLD# pulled up; set QE for quad reads. Not at LCSC: global sourcing')
cap('+3V3', '100nF', '0603', 'mem', 'U4 bypass')
for n in ('FLASH_CS_N', 'FLASH_IO2', 'FLASH_IO3'): res('+3V3', n, '10k', 'mem')
part('Y1', 'Device:Crystal_GND24', '24MHz', 'Crystal:Crystal_SMD_2016-4Pin_2.0x1.6mm', 'mem',
     {'1': 'XTALI', '2': 'GND', '3': 'XTALO', '4': 'GND'}, Note='24 MHz, CL to match C load caps')
cap('XTALI', '12pF', '0603', 'mem', '24 MHz load (set from crystal CL)'); cap('XTALO', '12pF', '0603', 'mem', '24 MHz load')
part('Y2', 'Device:Crystal_Small', '32.768kHz', 'Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm', 'mem',
     {'1': 'RTC_XTALI', '2': 'RTC_XTALO'}, LCSC='C32346', MPN='Q13FC1350000400', Note='FC-135, CL 12.5 pF')
cap('RTC_XTALI', '18pF', '0603', 'mem', '32k load'); cap('RTC_XTALO', '18pF', '0603', 'mem', '32k load')
for k in range(3):
    pins = {}
    for e in range(4):
        i = k * 4 + e
        pins[str(e + 1)] = f'BOOT_CFG{i}'; pins[str(8 - e)] = 'GND'
    part(f'RN{k+1}', 'Device:R_Pack04', '10k', 'Resistor_SMD:R_Array_Convex_4x0603', 'mem', pins,
         Note='BOOT_CFG straps = 0: boot from FlexSPI1 NOR')
res('LED', 'LED_A', '1k', 'mem')
part('D2', 'Device:LED_Small', 'Green', 'LED_SMD:LED_0603_1608Metric', 'mem', {'1': 'GND', '2': 'LED_A'})

# power flags for nets driven only by passives / internal regulators
FLAG_NETS = ['GND', 'DCDC_DIG', 'DCDC_ANA', 'VDD_SNVS_ANA', 'VDD_SNVS_IN', 'ADC_VREFH', 'VDDA_ADC_3P3', 'VDD_MIPI_1P0', 'VDD_MIPI_1P8']
for i, n in enumerate(FLAG_NETS, start=1):
    part(f'#FLG{i:02d}', 'power:PWR_FLAG', 'PWR_FLAG', '', 'power', {'1': n})

# --------------------------------------------------------------------------- symbol library access
_libcache = {}
def lib_block(lib_id):
    lib, name = lib_id.split(':')
    if lib == 'rt1176-som': path = os.path.join(ROOT, 'lib', 'rt1176-som.kicad_sym')
    else: path = os.path.join(KLIB, lib + '.kicad_sym')
    s = _libcache.setdefault(path, open(path).read())
    i = s.find(f'\n  (symbol "{name}"'); assert i >= 0, lib_id
    d = 0; j = i + 1; ins = False
    while True:
        c = s[j]
        if c == '"' and s[j - 1] != '\\': ins = not ins
        elif not ins:
            if c == '(': d += 1
            elif c == ')':
                d -= 1
                if d == 0: break
        j += 1
    blk = s[i + 1:j + 1]
    assert '(extends' not in blk, lib_id
    return blk.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)

def lib_pins(lib_id, unit):
    blk = lib_block(lib_id); name = lib_id.split(':')[1]
    pins = {}
    for m in re.finditer(r'\(symbol "%s_(\d+)_(\d+)"' % re.escape(name), blk):
        u = int(m.group(1))
        if u not in (0, unit): continue
        st = m.start(); d = 0; j = st
        while True:
            if blk[j] == '(': d += 1
            elif blk[j] == ')':
                d -= 1
                if d == 0: break
            j += 1
        for p in re.finditer(r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\) \(length ([\d.]+)\)(.*?)\(number "([^"]*)"', blk[st:j], re.S):
            pins[p.group(6)] = (float(p.group(1)), float(p.group(2)), int(p.group(3)))
    return pins

# --------------------------------------------------------------------------- writer
SHEETS = [('edge', 'MicroMod edge, reset, boot, test pads', 2), ('mcu', 'RT1176 I/O', 3), ('power', 'RT1176 power', 4),
          ('mem', 'Flash, clocks, boot straps, LED', 5)]
ROOT_UUID = U('root')
FONT = '(effects (font (size 1.27 1.27)))'
G = 1.27
def snap(v): return round(round(v / G) * G, 4)

def label_dir(ang):
    # pin angle (direction from connection point toward the body) -> outward unit vector, label angle
    return {0: (-1, 0, 180), 180: (1, 0, 0), 90: (0, 1, 270), 270: (0, -1, 90)}[ang]

def emit_symbol(p, x, y, out, path):
    lib_id = p['lib']; unit = p['unit']; ref = p['ref']
    pins = lib_pins(lib_id, unit)
    sid = U('sym', ref, unit)
    ys = [-v[1] for v in pins.values()]
    big = len(pins) > 3
    ry = snap(y + min(ys) - (3.81 if big else 0)) if big else snap(y - 1.27)
    vy = snap(y + max(ys) + (3.81 if big else 0)) if big else snap(y + 1.27)
    rx = snap(x + (2.54 if not big else 0))
    flds = [('Reference', ref, rx, ry, ref.startswith('#')), ('Value', p['value'], rx, vy, ref.startswith('#')),
            ('Footprint', p['fp'], x, y, True), ('Datasheet', '', x, y, True)]
    for k, v in p['fields'].items():
        if v: flds.append((k, v, x, y, True))
    out.append(f'  (symbol (lib_id "{lib_id}") (at {x} {y} 0) (unit {unit}) (in_bom {"no" if ref.startswith("#") or ref.startswith("TP") or ref == "J1" else "yes"}) '
               f'(on_board {"no" if ref.startswith("#") else "yes"}) (dnp no) (uuid {sid})')
    for k, v, fx, fy, hide in flds:
        eff = '(effects (font (size 1.27 1.27)) hide)' if hide else FONT
        if not hide and k in ('Reference', 'Value') and len(pins) <= 3: eff = '(effects (font (size 1.27 1.27)) (justify left))'
        out.append(f'    (property "{k}" "{v}" (at {fx} {fy} 0) {eff})')
    for num in pins: out.append(f'    (pin "{num}" (uuid {U("pin", ref, unit, num)}))')
    out.append(f'    (instances (project "{PROJECT}" (path "{path}" (reference "{ref}") (unit {unit}))))')
    out.append('  )')
    # wires + labels / no-connects
    netmap = p['pins'] if p['pins'] is not None else {b: U1[b] for b in pins}
    for num, (px, py, ang) in pins.items():
        cx, cy = snap(x + px), snap(y - py)
        net = netmap.get(num)
        if net is None:
            out.append(f'  (no_connect (at {cx} {cy}) (uuid {U("nc", ref, unit, num)}))'); continue
        dx, dy, la = label_dir(ang)
        ex, ey = snap(cx + dx * 2.54), snap(cy + dy * 2.54)
        out.append(f'  (wire (pts (xy {cx} {cy}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {U("w", ref, unit, num)}))')
        just = {0: 'left', 180: 'right', 90: 'left', 270: 'right'}[la]
        out.append(f'  (global_label "{net}" (shape passive) (at {ex} {ey} {la}) (fields_autoplaced) '
                   f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {U("gl", ref, unit, num)}) '
                   f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {ex} {ey} 0) (effects (font (size 1.27 1.27)) hide)))')

def bbox(p):
    """Extent of symbol + wires + labels, schematic orientation, relative to the symbol origin."""
    pins = lib_pins(p['lib'], p['unit'])
    netmap = p['pins'] if p['pins'] is not None else {b: U1[b] for b in pins}
    l = r = t = b = 0.0
    for num, (px, py, ang) in pins.items():
        cx, cy = px, -py
        L = 2.54 + (len(netmap.get(num) or '') * 1.05 + 2.5 if netmap.get(num) else 1.0)
        dx, dy, _ = label_dir(ang)
        ex, ey = cx + dx * L, cy + dy * L
        l = min(l, cx, ex - 1.5); r = max(r, cx, ex + 1.5); t = min(t, cy, ey - 1.5); b = max(b, cy, ey + 1.5)
    return (l - 2, r + 2, t - 5, b + 5)

def layout(sheet_parts, width):
    """Shelf packing, left to right then down. Returns {id(part): (x, y)}."""
    pos = {}; x0 = 20.32; y0 = 38.1; x = x0; y = y0; shelf = 0
    for p in sheet_parts:
        l, r, t, b = bbox(p); w = r - l; h = b - t
        if x + w > width - 15 and x > x0: x = x0; y += shelf + 5.08; shelf = 0
        pos[id(p)] = (snap(x - l), snap(y - t)); x += w + 5.08; shelf = max(shelf, h)
    return pos, y + shelf

NOTES = {
    'edge': ['MicroMod processor card edge: SparkFun MicroMod Teensy pinout (docs/PINOUT.md).',
             'Pins 13/15/21/23 carry SAI4 (AUD2) instead of RTS1/CTS1/SWDCK/SWDIO; SWD is on test pads TP1/TP2.',
             'RESET# -> U2 manual reset; U2 holds POR_B low through power-up (open drain, POR_B has an internal 100k pull-up).',
             'BOOT# -> BOOT_MODE1 and, inverted by U3, BOOT_MODE0: released = 10 internal boot, held = 01 USB serial downloader.'],
    'mcu': ['All I/O banks at 3.3 V. Unused pads float (pad keepers). BOOT_CFG pads only go to the straps on the Flash sheet.'],
    'power': ['3.3 V only from the carrier. RT1176 internal DCDC makes DCDC_DIG (1.0/1.1 V core) and DCDC_ANA (1.8 V).',
              '0402 parts sit under the BGA at the ball named in their Note field; 0603/0805 bulk next to the BGA.'],
    'mem': ['FlexSPI1 port A: the boot ROM default. DQS (GPIO_SD_B2_05) is left open for loopback read sampling.',
            'BOOT_CFG straps all 0 = boot device FlexSPI NOR (used only while BT_FUSE_SEL = 0).'],
}

def write_sheet(key, title, page, path):
    sp = [p for p in parts if p['sheet'] == key]
    big = [p for p in sp if p['lib'].startswith('rt1176-som:') or p['ref'].startswith('U')]
    small = [p for p in sp if p not in big]
    width = 594 if key in ('mcu', 'power') else 420
    pos, ybig = layout(big, width)
    pos2, yend = layout(small, width)
    for k, (x, y) in pos2.items(): pos[k] = (x, snap(y + ybig - 30))
    paper = 'A2' if key in ('mcu', 'power') else 'A3'
    out = [f'(kicad_sch (version 20230121) (generator eeschema)', f'  (uuid {U("sheet", key)})', f'  (paper "{paper}")',
           f'  (title_block (title "{TITLE}: {title}") (rev "{REV}") (company "markrlupton") (comment 1 "Generated by tools/schgen.py; do not edit by hand"))',
           '  (lib_symbols']
    for lid in sorted({p['lib'] for p in sp}): out.append('    ' + lib_block(lid).replace('\n', '\n  '))
    out.append('  )')
    for i, t in enumerate(NOTES.get(key, [])):
        out.append(f'  (text "{t}" (at 25.4 {20.32 + i * 3.81} 0) (effects (font (size 1.778 1.778)) (justify left bottom)) (uuid {U("txt", key, i)}))')
    for p in sp:
        x, y = pos[id(p)]; emit_symbol(p, x, y, out, path)
    out.append(f'  (sheet_instances (path "/" (page "{page}")))' if False else '')
    out.append(')')
    open(os.path.join(ROOT, 'sheets', f'{key}.kicad_sch'), 'w').write('\n'.join(l for l in out if l) + '\n')

def write_root():
    out = ['(kicad_sch (version 20230121) (generator eeschema)', f'  (uuid {ROOT_UUID})', '  (paper "A4")',
           f'  (title_block (title "{TITLE}") (rev "{REV}") (company "markrlupton") (comment 1 "MicroMod processor card, NXP i.MX RT1176"))',
           '  (lib_symbols)']
    for i, (key, title, page) in enumerate(SHEETS):
        x, y = 30.48 + (i % 2) * 100.33, 40.64 + (i // 2) * 50.8
        sid = U('sheetsym', key)
        out.append(f'  (sheet (at {x} {y}) (size 76.2 30.48) (fields_autoplaced) (stroke (width 0.1524) (type solid)) '
                   f'(fill (color 0 0 0 0.0000)) (uuid {sid})')
        out.append(f'    (property "Sheetname" "{title}" (at {x} {y - 0.7} 0) (effects (font (size 1.27 1.27)) (justify left bottom)))')
        out.append(f'    (property "Sheetfile" "sheets/{key}.kicad_sch" (at {x} {y + 31.1} 0) (effects (font (size 1.27 1.27)) (justify left top)))')
        out.append(f'    (instances (project "{PROJECT}" (path "/{ROOT_UUID}" (page "{page}"))))')
        out.append('  )')
    out.append('  (sheet_instances (path "/" (page "1")))')
    out.append(')')
    open(os.path.join(ROOT, f'{PROJECT}.kicad_sch'), 'w').write('\n'.join(out) + '\n')

def write_project():
    pro = os.path.join(ROOT, f'{PROJECT}.kicad_pro')
    if not os.path.exists(pro):
        json.dump({"meta": {"filename": f"{PROJECT}.kicad_pro", "version": 1}, "schematic": {}, "boards": [], "sheets": [],
                   "text_variables": {}}, open(pro, 'w'), indent=2)
    open(os.path.join(ROOT, 'sym-lib-table'), 'w').write(
        '(sym_lib_table\n  (lib (name "rt1176-som")(type "KiCad")(uri "${KIPRJMOD}/lib/rt1176-som.kicad_sym")(options "")(descr "project"))\n)\n')
    open(os.path.join(ROOT, 'fp-lib-table'), 'w').write(
        '(fp_lib_table\n  (lib (name "rt1176-som")(type "KiCad")(uri "${KIPRJMOD}/lib/rt1176-som.pretty")(options "")(descr "project"))\n)\n')

if __name__ == '__main__':
    os.makedirs(os.path.join(ROOT, 'sheets'), exist_ok=True)
    for key, title, page in SHEETS:
        write_sheet(key, title, page, f'/{ROOT_UUID}/{U("sheetsym", key)}')
    write_root(); write_project()
    json.dump({p['ref'] + (f'.{p["unit"]}' if p['ref'] == 'U1' else ''): {'value': p['value'], 'pins': p['pins'] if p['pins'] is not None else 'U1'}
               for p in parts}, open(os.path.join(DATA, 'design_nets.json'), 'w'), indent=0)
    json.dump(U1, open(os.path.join(DATA, 'u1_nets.json'), 'w'), indent=0)
    print(f'{len(parts)} symbols, sheets:', ', '.join(k for k, _, _ in SHEETS))
