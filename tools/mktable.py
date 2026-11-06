import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); DATA=os.path.join(HERE,'data'); sys.path.insert(0,HERE)
import sys,json; sys.path.insert(0,'.')
from pinmap import PINMAP, INTERNAL
d=json.load(open(os.path.join(DATA,'mcu_maps.json'))); balls=list(d['ours'].values())[0]
n2b={n:b for b,ns in balls.items() for n in ns}
L=["| Pin | MicroMod | Teensy | RT1176 pad | Ball | Function | Notes |","|---|---|---|---|---|---|---|"]
for p in sorted(PINMAP):
    nm,tp,pad,fn,note=PINMAP[p]; ball=n2b.get(pad,'')
    if pad=='SUPERVISOR_MR': pad,ball='POR_B (via reset supervisor)','T10'
    if pad in('GND','+3V3'): ball=''
    L.append(f"| {p} | {nm} | {tp} | {pad.replace('GPIO_','')} | {ball} | {fn} | {note} |")
L.append("\nPins 24–31 are the key notch.\n\n### Card-internal pads\n\n| RT1176 pad | Ball | Use |\n|---|---|---|")
for pad,u in INTERNAL.items(): L.append(f"| {pad.replace('GPIO_','')} | {n2b.get(pad,'')} | {u} |")
open(os.path.join(ROOT,'docs','PINOUT.md'),'w').write('\n'.join(L)+'\n')
