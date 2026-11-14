"""BOM for distributor upload tools (Octopart, Mouser, DigiKey, Newark): fab/bom-distributors.csv

  python3 tools/bom_dist.py        (after tools/fab.py)

Each line has one manufacturer part number. Where the JLC BOM uses a part only LCSC stocks (Fenghua, UNI-ROYAL,
Sunlord ferrites, YXC crystal), this uses a same-spec part the western distributors carry. Footprints are unchanged.
'Qty per board' is for one card; 'Qty for 5 boards' adds spares for hand assembly (10 extra of each passive, 1 extra
of each IC, LED and crystal) - pick whichever column the upload tool asks for.
"""
import csv, os, re
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
BOARDS = 5

# (value, footprint) -> (manufacturer, MPN, description)
PARTS = {
    ('22uF', 'C_0805_2012Metric'): ('Samsung', 'CL21A226MAQNNNE', 'Cap ceramic 22 uF 25 V X5R 0805'),
    ('10uF', 'C_0805_2012Metric'): ('Samsung', 'CL21A106KAYNNNE', 'Cap ceramic 10 uF 25 V X5R 0805'),
    ('100nF', 'C_0603_1608Metric'): ('Yageo', 'CC0603KRX7R9BB104', 'Cap ceramic 100 nF 50 V X7R 0603'),
    ('4.7uF', 'C_0603_1608Metric'): ('Samsung', 'CL10A475KO8NNNC', 'Cap ceramic 4.7 uF 16 V X5R 0603'),
    ('10uF', 'C_0603_1608Metric'): ('Samsung', 'CL10A106KP8NNNC', 'Cap ceramic 10 uF 10 V X5R 0603'),
    ('1uF', 'C_0402_1005Metric'): ('Samsung', 'CL05A105KA5NQNC', 'Cap ceramic 1 uF 25 V X5R 0402'),
    ('100nF', 'C_0402_1005Metric'): ('Samsung', 'CL05B104KO5NNNC', 'Cap ceramic 100 nF 16 V X7R 0402'),
    ('2.2uF', 'C_0402_1005Metric'): ('Samsung', 'CL05A225MQ5NSNC', 'Cap ceramic 2.2 uF 6.3 V X5R 0402'),
    ('4.7uF', 'C_0402_1005Metric'): ('Samsung', 'CL05A475MP5NRNC', 'Cap ceramic 4.7 uF 10 V X5R 0402'),
    ('220nF', 'C_0402_1005Metric'): ('Samsung', 'CL05B224KO5NNNC', 'Cap ceramic 220 nF 16 V X7R 0402'),
    ('12pF', 'C_0402_1005Metric'): ('Murata', 'GRM1555C1H120JA01D', 'Cap ceramic 12 pF 50 V C0G 0402'),
    ('18pF', 'C_0402_1005Metric'): ('Murata', 'GRM1555C1H180JA01D', 'Cap ceramic 18 pF 50 V C0G 0402'),
    ('10k', 'R_0402_1005Metric'): ('Yageo', 'RC0402FR-0710KL', 'Res 10 k 1% 0402'),
    ('10k', 'R_0603_1608Metric'): ('Yageo', 'RC0603FR-0710KL', 'Res 10 k 1% 0603'),
    ('1k', 'R_0603_1608Metric'): ('Yageo', 'RC0603FR-071KL', 'Res 1 k 1% 0603'),
    ('4.7k', 'R_0603_1608Metric'): ('Yageo', 'RC0603FR-074K7L', 'Res 4.7 k 1% 0603'),
    ('120R@100MHz', 'L_0603_1608Metric'): ('Murata', 'BLM18PG121SN1D', 'Ferrite bead 120 R @ 100 MHz 2 A 0603'),
    ('4.7uH', 'L_Changjiang_FNR4030S'): ('Sunlord', 'SWPA4030S4R7MT', 'Inductor 4.7 uH 2 A shielded 4x4x3 mm'),
    ('Green', 'LED_0603_1608Metric'): ('Lite-On', 'LTST-C191KGKT', 'LED green 0603'),
    ('BAT54C', 'SOT-23'): ('Nexperia', 'BAT54C,215', 'Schottky dual common cathode 30 V SOT-23'),
    ('MIMXRT1176DVMAB', 'MAPBGA_14x14mm_Layout17x17_P0.8mm'): ('NXP', 'MIMXRT1176DVMAB', 'i.MX RT1176 MCU, 1 GHz M7 + 400 MHz M4, 289 MAPBGA'),
    ('TPS3808G30DBVR', 'SOT-23-6'): ('Texas Instruments', 'TPS3808G30DBVR', 'Voltage supervisor 2.79 V, manual reset, SOT-23-6'),
    ('SN74LVC1G04DBVR', 'SOT-23-5'): ('Texas Instruments', 'SN74LVC1G04DBVR', 'Single inverter SOT-23-5'),
    ('GD25Q128EQIGR', 'USON-8-1EP_4x4mm_P0.8mm_EP2.3x3mm_GigaDevice'): ('GigaDevice', 'GD25Q128EQIGR', 'QSPI NOR flash 128 Mbit (16 MB) USON-8 4x4'),
    ('24MHz', 'Crystal_SMD_2016-4Pin_2.0x1.6mm'): ('Abracon', 'ABM11W-24.0000MHZ-8-D1X-T3', 'Crystal 24 MHz 8 pF 10 ppm 2.0x1.6 mm'),
    ('32.768kHz', 'Crystal_SMD_3215-2Pin_3.2x1.5mm'): ('Epson', 'Q13FC1350000400', 'Crystal 32.768 kHz 12.5 pF FC-135 3.2x1.5 mm'),
}
PASSIVE = re.compile(r'^(C|R|FB)\d')

def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'fab', 'bom-jlc.csv'))))
    out = []
    for i, r in enumerate(rows, 1):
        mfr, mpn, desc = PARTS[(r['Comment'], r['Footprint'])]
        q = int(r['Qty']); first = r['Designator'].split(',')[0]
        spare = 10 if PASSIVE.match(first) else 1
        out.append([i, q, q * BOARDS + spare, mfr, mpn, desc, r['Designator'].replace(',', ' '), r['Footprint'], r['Side']])
    path = os.path.join(ROOT, 'fab', 'bom-distributors.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['Line', 'Qty per board', f'Qty for {BOARDS} boards', 'Manufacturer', 'Manufacturer Part Number', 'Description',
                    'Designators', 'Footprint', 'Side'])
        w.writerows(out)
    print(f'{path}: {len(out)} lines, {sum(o[1] for o in out)} parts per board')

if __name__ == '__main__':
    main()
