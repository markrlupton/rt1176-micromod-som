"""Stage 4: fabrication and assembly outputs for JLCPCB.

  python3 tools/fab.py        (after the board is routed; writes fab/ and the zips in build/)

fab/gerbers/        Gerbers (Protel extensions) + Excellon drill, PTH and NPTH separate. Zip: fab/rt1176-micromod-som-gerbers.zip
fab/stencil-hand/   F.Paste without BGA apertures (the BGA is soldered flux-only by hand) + B.Paste
fab/bom-jlc.csv     JLC BOM: Comment, Designator, Footprint, LCSC Part #, plus MPN and notes
fab/cpl-jlc.csv     JLC pick-and-place: Designator, Mid X, Mid Y, Layer, Rotation
fab/assembly-top.pdf, fab/assembly-bottom.pdf   placement drawings with reference designators (bottom is mirrored)
fab/drc.txt         KiCad DRC report of the board as released
Silkscreen: reference designators and values are left off (there is no room for legible text around a 14 mm BGA on
a 22.8 mm card); the assembly drawings carry the designators instead. Footprint outlines and pin-1 marks stay.
"""
import collections, csv, json, os, re, shutil, subprocess, sys, tempfile, zipfile
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from pcbgen import OUT
FAB = os.path.join(ROOT, 'fab')
NAME = 'rt1176-micromod-som'
LAYERS = ['F.Cu', 'In1.Cu', 'In2.Cu', 'In3.Cu', 'In4.Cu', 'B.Cu', 'F.Paste', 'B.Paste', 'F.Silkscreen', 'B.Silkscreen',
          'F.Mask', 'B.Mask', 'Edge.Cuts']

# LCSC numbers, by (value, footprint). Basic parts unless noted. Checked on jlcpcb.com / lcsc.com, Nov 2026.
LCSC = {
    ('100nF', 'C_0402_1005Metric'): ('C1525', 'Samsung CL05B104KO5NNNC 16 V X7R'),
    ('1uF', 'C_0402_1005Metric'): ('C52923', 'Samsung CL05A105KA5NQNC 25 V X5R'),
    ('2.2uF', 'C_0402_1005Metric'): ('C12530', 'Samsung CL05A225MQ5NSNC 6.3 V X5R'),
    ('4.7uF', 'C_0402_1005Metric'): ('C23733', 'Samsung CL05A475MP5NRNC 10 V X5R'),
    ('220nF', 'C_0402_1005Metric'): ('C16772', 'Samsung CL05B224KO5NNNC 16 V X7R'),
    ('12pF', 'C_0402_1005Metric'): ('C1547', 'FH 0402CG120J500NT C0G'),
    ('18pF', 'C_0402_1005Metric'): ('C1549', 'FH 0402CG180J500NT C0G'),
    ('100nF', 'C_0603_1608Metric'): ('C14663', 'Yageo CC0603KRX7R9BB104'),
    ('4.7uF', 'C_0603_1608Metric'): ('C19666', 'Samsung CL10A475KO8NNNC'),
    ('10uF', 'C_0603_1608Metric'): ('C19702', 'Samsung CL10A106KP8NNNC'),
    ('22uF', 'C_0805_2012Metric'): ('C45783', 'Samsung CL21A226MAQNNNE 25 V'),
    ('10uF', 'C_0805_2012Metric'): ('C15850', 'Samsung CL21A106KAYNNNE 25 V'),
    ('10k', 'R_0402_1005Metric'): ('C25744', 'UNI-ROYAL 0402WGF1002TCE'),
    ('10k', 'R_0603_1608Metric'): ('C25804', 'UNI-ROYAL 0603WAF1002T5E'),
    ('1k', 'R_0603_1608Metric'): ('C21190', 'UNI-ROYAL 0603WAF1001T5E'),
    ('4.7k', 'R_0603_1608Metric'): ('C23162', 'UNI-ROYAL 0603WAF4701T5E'),
    ('Green', 'LED_0603_1608Metric'): ('C72043', 'Everlight 19-217/GHC-YR1S2/3T'),
    ('120R@100MHz', 'L_0603_1608Metric'): ('C12391', 'Sunlord GZ1608D121TF'),
    ('24MHz', 'Crystal_SMD_2016-4Pin_2.0x1.6mm'): ('C108160', 'YXC X201624MMD4SI, 10 pF CL, extended part'),
}
NOT_ASSEMBLED = ('J1', 'TP')          # gold fingers and bare test pads

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: print(r.stdout, r.stderr); raise SystemExit(f'failed: {" ".join(cmd)}')
    return r.stdout

def bom(b, fpinfo):
    groups = collections.OrderedDict()
    for fp in sorted(b.GetFootprints(), key=lambda f: (f.GetReference()[0], int(re.sub(r'\D', '', f.GetReference()) or 0))):
        ref = fp.GetReference()
        if ref.startswith(NOT_ASSEMBLED): continue
        info = fpinfo[ref]; fpn = info['fp'].split(':')[1]
        lcsc = info['fields'].get('LCSC', ''); mpn = info['fields'].get('MPN', ''); note = ''
        if not lcsc and (info['value'], fpn) in LCSC: lcsc, mpn = LCSC[(info['value'], fpn)][0], LCSC[(info['value'], fpn)][1]
        if ref == 'U1': note = 'not stocked at LCSC: buy MIMXRT1176DVMAB (or DVMAA) from DigiKey/Mouser, consign or global sourcing'
        if ref == 'U4': note = 'GD25Q128EQIGR not listed at LCSC: buy from DigiKey/Mouser, consign or global sourcing'
        side = 'bottom' if fp.GetLayer() == pcbnew.B_Cu else 'top'
        key = (info['value'], fpn, lcsc, mpn, note)
        groups.setdefault(key, {'refs': [], 'sides': set()})
        groups[key]['refs'].append(ref); groups[key]['sides'].add(side)
    rows = []
    for (val, fpn, lcsc, mpn, note), g in groups.items():
        rows.append([val, ','.join(g['refs']), fpn, lcsc, mpn, len(g['refs']), '/'.join(sorted(g['sides'])), note])
    with open(os.path.join(FAB, 'bom-jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #', 'MPN', 'Qty', 'Side', 'Note'])
        w.writerows(rows)
    return rows

def cpl(b):
    tmp = tempfile.mkdtemp(); pos = os.path.join(tmp, 'pos.csv')
    run(['kicad-cli', 'pcb', 'export', 'pos', '--side', 'both', '--format', 'csv', '--units', 'mm', '-o', pos, OUT])
    rows = list(csv.DictReader(open(pos)))
    with open(os.path.join(FAB, 'cpl-jlc.csv'), 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        n = 0
        for r in rows:
            if r['Ref'].startswith(NOT_ASSEMBLED): continue
            w.writerow([r['Ref'], f"{float(r['PosX']):.4f}mm", f"{float(r['PosY']):.4f}mm", 'Top' if r['Side'] == 'top' else 'Bottom', f"{float(r['Rot']):.1f}"])
            n += 1
    return n

def hand_build(rows):
    """docs/HAND_BUILD.md: build order, profiles and the part list by side (regenerated from the BOM)"""
    def table(side):
        out = ['| Ref | Part | Footprint | Qty |', '|---|---|---|---|']
        for val, refs, fpn, lcsc, mpn, qty, sides, note in rows:
            mine = [r for r in refs.split(',') if side in sides_of[r]]
            if mine: out.append(f'| {", ".join(mine)} | {val} | {fpn.split("_")[0] if fpn.startswith(("C_", "R_", "L_", "LED_")) else fpn} {"(" + fpn.split("_")[1] + ")" if fpn.startswith(("C_", "R_", "L_", "LED_")) else ""} | {len(mine)} |')
        return '\n'.join(out)
    b = pcbnew.LoadBoard(OUT)
    sides_of = {fp.GetReference(): ('bottom' if fp.GetLayer() == pcbnew.B_Cu else 'top') for fp in b.GetFootprints()}
    txt = f"""# Hand build: RT1176 MicroMod card

Generated by `tools/fab.py` from the board and BOM. Placement drawings: `fab/assembly-top.pdf` and
`fab/assembly-bottom.pdf` (the bottom one is mirrored, so it matches the board turned over). The silkscreen carries
outlines and pin-1 marks only; use the drawings for designators.

## Order of work

**1. Top side first, on the hot plate.** The bottom is still bare, so the card sits flat on the plate.
- Paste the top with the hand-build stencil (`fab/stencil-hand/...-hand-F_Paste.gtp`): it has **no apertures for the BGA**.
- BGA: tacky flux only (e.g. Amtech NC-559), a thin even film on the pads. The balls bring their own solder.
- Place the BGA by the silkscreen outline and the pin-1 mark (A1 is at the top-right corner, beside the right-band caps).
- Place the other top parts (bulk caps, inductor, both crystals, ferrites, and C52, the one top-side 0402, beside Y2).
- Reflow: preheat to about 150 to 180 °C over 90 s, then up to 235 to 245 °C. Watch for the BGA to drop slightly and
  self-centre, hold about 30 s, then let it cool without touching it.

**2. Bottom side second, with low-temperature paste and hot air.**
- Paste: Sn42Bi57.6Ag0.4 (melts about 138 °C), bottom stencil `...-hand-B_Paste.gbp`.
- Rest the card BGA-down on two spacer strips (scrap FR4 or aluminium) on the plate, so nothing on top touches.
- Preheat at 100 to 120 °C. Reflow the bottom parts with hot air at about 200 to 220 °C, keeping the air moving and off
  the area right over the BGA as much as you can. The BGA's SAC305 balls melt at 217 °C, so they stay put.
- Bismuth solder is more brittle under shock and vibration. Fine for a bench card; a card for the car should be built
  with standard solder on both sides (JLC assembly or an oven).

**3. Inspect and clean.** Flux off with IPA. Look along the BGA edges with a loupe for even collapse and no bridges
(you can't see the inner balls; the electrical checks below are the test).

## First power-up

1. Before power: ohmmeter, +3V3 to GND (fingers 2/74 to any GND finger). Expect it to climb slowly (caps charging),
   not a dead short.
2. Bench supply 3.3 V, current limit about 100 mA, into the 3.3 V fingers (carrier or clip leads).
3. Current should settle to tens of mA. If it sits at the limit, power off and look for a short.
4. Rails: DCDC_ANA about 1.8 V (C21 / FB1), DCDC_DIG about 1.0 to 1.1 V (C11, C12, C13).
5. 24 MHz: scope probe (10x) on Y1 pad 3 (XTALO) should show a sine of a few hundred mV.
6. SWD: the test pads on the bottom edge (TP1 SWDIO, TP2 SWCLK, TP3 RESET#). Connect a debugger and read the chip ID.
7. Serial downloader: hold BOOT# (TP4, or MicroMod pin 11 on the carrier) low through reset; the chip enumerates over USB1 as
   an NXP SDP/HID device. Program the flash from there (MCUXpresso Secure Provisioning or blhost).

## Parts, top side

{table('top')}

## Parts, bottom side

{table('bottom')}
"""
    open(os.path.join(ROOT, 'docs', 'HAND_BUILD.md'), 'w').write(txt)

def main():
    fpinfo = json.load(open(os.path.join(HERE, 'data', 'design_fp.json')))
    if os.path.exists(FAB): shutil.rmtree(FAB)
    gdir = os.path.join(FAB, 'gerbers'); sdir = os.path.join(FAB, 'stencil-hand'); os.makedirs(gdir); os.makedirs(sdir)
    b = pcbnew.LoadBoard(OUT)
    # DRC report of the released board
    pcbnew.WriteDRCReport(b, os.path.join(FAB, 'drc.txt'), pcbnew.EDA_UNITS_MILLIMETRES, True)
    drc = open(os.path.join(FAB, 'drc.txt')).read()
    counts = collections.Counter(re.findall(r'^\[(\w+)\]', drc, re.M))
    bad = {k: v for k, v in counts.items() if k not in ('lib_footprint_issues', 'silk_overlap', 'silk_over_copper', 'silk_edge_clearance')}
    assert not bad and '** Found 0 unconnected pads **' in drc, f'board is not clean: {bad}'
    # Gerbers and drill
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '-o', gdir + '/', '--layers', ','.join(LAYERS), '--exclude-refdes', '--exclude-value',
         '--no-netlist', OUT])                      # (no soldermask subtraction: it needs negative-polarity silk; JLC clips silk on pads anyway)
    run(['kicad-cli', 'pcb', 'export', 'drill', '-o', gdir + '/', '--format', 'excellon', '--drill-origin', 'absolute',
         '--excellon-units', 'mm', '--excellon-zeros-format', 'decimal', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', OUT])
    for f in os.listdir(gdir):                      # the board has no unplated holes: drop the empty NPTH files
        if 'NPTH' in f: os.remove(os.path.join(gdir, f))
    files = sorted(os.listdir(gdir))
    with zipfile.ZipFile(os.path.join(FAB, f'{NAME}-gerbers.zip'), 'w', zipfile.ZIP_DEFLATED) as z:
        for f in files: z.write(os.path.join(gdir, f), f)
    # hand-build stencil: top paste without the BGA (flux only), bottom paste as is
    tmpb = os.path.join(tempfile.mkdtemp(), 'stencil.kicad_pcb')
    u1 = b.FindFootprintByReference('U1')
    for p in u1.Pads():
        ls = p.GetLayerSet(); ls.RemoveLayer(pcbnew.F_Paste); p.SetLayerSet(ls)
    pcbnew.SaveBoard(tmpb, b)
    run(['kicad-cli', 'pcb', 'export', 'gerbers', '-o', sdir + '/', '--layers', 'F.Paste,B.Paste,Edge.Cuts', '--no-netlist', tmpb])
    for f in os.listdir(sdir): os.rename(os.path.join(sdir, f), os.path.join(sdir, f.replace('stencil', NAME + '-hand')))
    # assembly drawings (fab layers carry the designators)
    run(['kicad-cli', 'pcb', 'export', 'pdf', '-o', os.path.join(FAB, 'assembly-top.pdf'), '--layers', 'F.Fab,F.Courtyard,Edge.Cuts',
         '--exclude-value', '--black-and-white', OUT])
    run(['kicad-cli', 'pcb', 'export', 'pdf', '-o', os.path.join(FAB, 'assembly-bottom.pdf'), '--layers', 'B.Fab,B.Courtyard,Edge.Cuts',
         '--exclude-value', '--black-and-white', '--mirror', OUT])
    b = pcbnew.LoadBoard(OUT)
    rows = bom(b, fpinfo); n = cpl(b)
    print(f'gerbers: {len(files)} files; BOM {len(rows)} lines / {sum(r[5] for r in rows)} parts; CPL {n} placements')
    hand_build(rows)
    missing = [r for r in rows if not r[3]]
    for r in missing: print('  no LCSC number:', r[1], r[0], '-', r[7] or 'check')

if __name__ == '__main__':
    main()
