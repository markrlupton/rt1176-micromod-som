"""Check the generated schematic: export its netlist with kicad-cli and compare it to the design data.

  python3 tools/schcheck.py

Checks
  1. Every net in the design (tools/schgen.py) appears in the schematic netlist with exactly the same pins.
  2. No net has a single connection, except no-connect pins.
  3. Every net with a power-input pin has a power source (power_out pin or PWR_FLAG).
  4. All 289 RT1176 balls are present; every MicroMod pin's net matches tools/pinmap.py.
  5. NXP power rules: each supply ball sits on the rail the design guide asks for.
Exit code 1 on any failure."""
import collections, json, os, subprocess, sys, tempfile
import xml.etree.ElementTree as ET
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); DATA = os.path.join(HERE, 'data')
sys.path.insert(0, HERE)

def main():
    tmp = tempfile.mkdtemp(); net = os.path.join(tmp, 'net.xml')
    subprocess.run(['kicad-cli', 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', net,
                    os.path.join(ROOT, 'rt1176-micromod-som.kicad_sch')], check=True, capture_output=True)
    r = ET.parse(net).getroot()
    nets = {}; ptype = {}
    for n in r.iter('net'):
        nodes = set()
        for nd in n.iter('node'):
            nodes.add((nd.get('ref'), nd.get('pin'))); ptype[(nd.get('ref'), nd.get('pin'))] = nd.get('pintype', '')
        nets[n.get('name').lstrip('/')] = nodes
    fails = []
    # expected nets
    design = json.load(open(os.path.join(DATA, 'design_nets.json'))); u1 = json.load(open(os.path.join(DATA, 'u1_nets.json')))
    exp = collections.defaultdict(set)
    for key, d in design.items():
        ref = key.split('.')[0]
        if ref.startswith('#'): continue
        pins = u1 if d['pins'] == 'U1' else d['pins']
        for pin, n in pins.items():
            if n: exp[n].add((ref, pin))
    got = {n: {x for x in v if not x[0].startswith('#')} for n, v in nets.items() if not n.startswith('unconnected')}
    for n in sorted(set(exp) | set(got)):
        if exp.get(n, set()) != got.get(n, set()):
            fails.append(f'net {n}: missing {sorted(exp.get(n, set()) - got.get(n, set()))[:6]} extra {sorted(got.get(n, set()) - exp.get(n, set()))[:6]}')
    # single-connection nets
    for n, v in nets.items():
        if n.startswith('unconnected'): continue
        real = {x for x in v if not x[0].startswith('#')}
        if len(real) < 2: fails.append(f'net {n} has only {sorted(real)}')
    # power sources (PWR_FLAG symbols are not exported to the netlist: read them from the power sheet)
    import re
    sheet = open(os.path.join(ROOT, 'sheets', 'power.kicad_sch')).read()
    flagged = set()
    for blk in sheet.split('(symbol (lib_id "power:PWR_FLAG")')[1:]:
        ref = re.search(r'\(reference "(#FLG\d+)"', blk).group(1)
        flagged.add(dict((k, d['pins']['1']) for k, d in design.items() if k.startswith('#FLG'))[ref])
    for n, v in nets.items():
        types = {ptype[x] for x in v}
        if 'power_in' in types and not ({'power_out'} & types) and n not in flagged:
            fails.append(f'net {n}: power input with no source')
    # U1 coverage
    u1pins = {p for v in nets.values() for (ref, p) in v if ref == 'U1'}
    if len(u1pins) != 289: fails.append(f'U1 has {len(u1pins)} pins in netlist (expected 289)')
    # MicroMod pins vs pinmap
    from pinmap import PINMAP
    import schgen
    for pin in PINMAP:
        want = schgen.EDGE_NET[pin] if PINMAP[pin][0] not in ('GND', '3.3V') else ('GND' if PINMAP[pin][0] == 'GND' else '+3V3')
        have = [n for n, v in nets.items() if ('J1', str(pin)) in v]
        if have != [want]: fails.append(f'J1 pin {pin}: {have} != {want}')
    # NXP power rules
    balls = json.load(open(os.path.join(DATA, 'rt1176_balls.json')))
    ball_net = {p: n for n, v in nets.items() for (ref, p) in v if ref == 'U1'}
    rules = {'VSS': 'GND', 'DCDC_GND': 'GND', 'TEST_MODE': 'GND', 'DCDC_IN': '+3V3', 'DCDC_IN_Q': '+3V3', 'VDD_LPSR_IN': '+3V3',
             'VDD_SOC_IN': 'DCDC_DIG', 'DCDC_DIG_SENSE': 'DCDC_DIG', 'DCDC_ANA_SENSE': 'DCDC_ANA', 'VDDA_1P8_IN': 'DCDC_ANA',
             'VDDA_ADC_1P8': 'DCDC_ANA', 'VDD_USB_1P8': 'DCDC_ANA', 'NVCC_SNVS': 'VDD_SNVS_ANA', 'VDD_USB_3P3': '+3V3'}
    for b, name in balls.items():
        if name in rules and ball_net.get(b) != rules[name]: fails.append(f'{name}@{b} on {ball_net.get(b)}, expected {rules[name]}')
        if name.startswith('NVCC_') and name != 'NVCC_SNVS' and ball_net.get(b) != '+3V3': fails.append(f'{name}@{b} not at 3.3 V')
    print(f'{len(nets)} nets, {len({x[0] for v in nets.values() for x in v})} references')
    if fails:
        print('FAIL'); [print('  ' + f) for f in fails]; sys.exit(1)
    print('PASS: netlist matches design data and pin map; no single-pin nets; all power inputs sourced; NXP rail rules met')

if __name__ == '__main__':
    main()
