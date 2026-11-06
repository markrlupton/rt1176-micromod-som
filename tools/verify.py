import os, sys
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE); DATA=os.path.join(HERE,'data'); sys.path.insert(0,HERE)
import json,re,sys,collections
sys.path.insert(0,'.')
from pinmap import PINMAP,INTERNAL,FORBIDDEN_FOR_EDGE
mux=json.load(open(os.path.join(DATA,'mux.json'))); p2b=json.load(open(os.path.join(DATA,'pad2ball.json')))
d=json.load(open(os.path.join(DATA,'mcu_maps.json'))); balls=list(d['ours'].values())[0]
name2ball={n:b for b,ns in balls.items() for n in ns}
nets=json.load(open(os.path.join(DATA,'teensy_nets.json')))
err=[];used=collections.Counter()
# all MicroMod pins Teensy implements must be present
teensy_pins=set()
for n,refs in nets.items():
    for r in refs:
        if r[0]=='J1':
            for p in r[2].split():
                if p.isdigit(): teensy_pins.add(int(p))
miss=sorted(teensy_pins-set(PINMAP)); print('Teensy pins missing from map:',miss)
for pin,(nm,tp,pad,fn,note) in PINMAP.items():
    if pad.startswith('GPIO_'):
        used[pad]+=1
        if pad not in p2b: err.append(f'{pin}: {pad} not a ball in symbol')
        if pad in FORBIDDEN_FOR_EDGE: err.append(f'{pin}: {pad} forbidden')
        for f in re.findall(r'(?:LPI2C|LPUART|LPSPI|SAI|CAN|USDHC|FLEXPWM|ADC)\w+',fn):
            if f not in mux[pad]: err.append(f'{pin}: {pad} lacks {f}')
    elif pad not in ('GND','+3V3','SUPERVISOR_MR'):
        if pad not in name2ball: err.append(f'{pin}: special {pad} not a ball')
for p in INTERNAL: used[p]+=1
dup=[p for p,c in used.items() if c>1]
print('duplicates',dup); print('errors',err or 'none')
# peripheral instance consistency
inst=collections.defaultdict(set)
for pin,(nm,tp,pad,fn,note) in PINMAP.items():
    m=re.match(r'(LPI2C\d|LPUART\d+|LPSPI\d|SAI\d|CAN\d|USDHC\d)',fn)
    if m: inst[m.group(1)].add((pin,fn.split()[0]))
for k,v in sorted(inst.items()): print(k,sorted(v))
