# RT1176 MicroMod card: design notes

A MicroMod processor card that carries an NXP i.MX RT1176 and uses the SparkFun MicroMod Teensy pinout, so it drops into the RaceLink intercom carrier's M.2 slot (rev A.2b and later) in place of the MicroMod Teensy.

Status: **stage 2 (schematic) for review.** The schematic is `rt1176-micromod-som.kicad_sch` (4 sheets, KiCad 7), plotted in `docs/schematic.pdf`.

## Decisions locked in

| Item | Decision |
|---|---|
| Scope | MCU core only: RT1176, QSPI flash, crystals, the processor's own power parts, reset supervisor, boot inverter, status LED. No Wi-Fi, IMU, motion controller or KL26 debugger (the carrier has Bluetooth, CAN, Ethernet and audio). |
| Pinout | Every MicroMod pin the SparkFun Teensy card uses gets the equivalent RT1176 function (54 pins, see `pintable.md`). The carrier's pins got first pick of pads. The four pins the Teensy leaves unconnected (13, 15, 21, 23) carry a **second SAI (SAI4)**: frame sync, data out, data in and bit clock. SWD moves to test pads on the card. |
| Size | 22.8 × 22 mm: the MicroMod outline widened 0.8 mm on the pin-1 side for 16 MB flash. Length, fingers and screw slot are standard. |
| Part sizes | 0402 only for decoupling under the BGA, 0603/0805 everywhere else, no 0201 planned. |
| Toolchain | KiCad 7 + Python generator + Freerouting, the same as the intercom carrier. |

## Mechanical

- **Outline:** taken from SparkFun's Teensy MicroMod board file. 22 × 22 mm, fingers at the bottom edge with the key notch at x = 13.6 mm, and a 3.5 mm half-hole for the M2.5 screw at x = 15 mm. The slot is 4 mm right of centre, not in the middle.
- **Fingers:** odd pins on top, even pins on the bottom, 0.5 mm pitch per side.
- **Board:** 6 layers, 0.8 mm thick (the M.2 standard), ENIG with bevelled gold fingers. All of these are standard JLC options, but gold fingers add cost.
- **Stack-up (proposed):** L1 signal, L2 GND, L3 signal (USB pair, BGA escape), L4 power (3.3 V, core rail island), L5 GND, L6 signal plus the decoupling parts.
- **BGA placement (corrected in v1):** the RT1176 is rotated 90° clockwise from its standard top view, so A1 is at the top-right, ball column 17 faces the fingers and row A is on the right. The v0 drawing had the ball map transposed, which is the chip seen from underneath and can't be built with a top-side part. Pads were then re-picked with `tools/optimize_pins.py`, which searches every peripheral instance and pad option and keeps each ball-to-finger route short.
- **Short and long routes:** the USB OTG1 balls (E16/E17) sit right above MicroMod pins 3/5. The longest routes are SAI4, whose only pads are on the left side of the BGA while its fingers are on the right, and the SDIO lines, the reverse. Neither is used by the rev A.2b carrier.
- **Fit on your carrier:** a 22 mm card fits rev A.2b unchanged. If the card ever needs to be wider:
  - About 0.8 mm is free on the pin-75 side before it overhangs D23 (SMA diode).
  - About 1 mm is free on the pin-1 side before it overhangs SW2 (PTS810).
  - Anything wider needs a keep-out on the rev B carrier.

## Power

The card takes **3.3 V only** from the carrier (pins 2 and 74), and the RT1176's internal DCDC makes the core and 1.8 V analog rails. There is no regulator on the card, which also removes the TPS62825 part-number trap from the G2 Nano.

| Rail | Source | Feeds | Notes |
|---|---|---|---|
| +3V3 | carrier | DCDC_IN, VDD_LPSR_IN, every NVCC_* bank, VDDA_ADC_3P3, VDD_USB_3P3 | Every I/O bank runs at 3.3 V, as MicroMod requires. Flash is a 3.3 V part. |
| DCDC_DIG (1.0/1.1 V) | RT1176 DCDC + 4.7 µH | VDD_SOC_IN | **3 × 22 µF 0805 + 0402s ≈ 70 µF**, meeting NXP's ~66 µF (the G2 Nano had ~31 µF) |
| DCDC_ANA (1.8 V) | RT1176 DCDC | VDDA_1P8_IN, VDD_USB_1P8, VDDA_ADC_1P8, ADC_VREFH (through an RC filter) | |
| VDD_SNVS_IN | BAT54C: diode-OR of +3V3 and MicroMod RTC_3V (pin 72) | RTC/SNVS | NVCC_SNVS tied to VDD_SNVS_ANA, per NXP's design guide |
| LPSR_ANA / LPSR_DIG / VDDA_1P0 | internal LDOs | — | caps under their balls this time (the G2 Nano's sat about 12 mm away) |
| DCDC_PSWITCH | 10k / 1 µF RC from +3V3 | | 10 ms, inside NXP's 5–40 ms window |

**Current draw (estimate):** roughly 130–200 mA from 3.3 V with the M7 at 1 GHz and the M4 doing light work. That's somewhat more than the Teensy 4's 100–150 mA. The carrier's +3V3D AP2114H LDO is budgeted at 300 mA, and its README already flags that LDO's temperature in a hot cabin. The card adds load to that same rail, so a buck on +3V3D is worth considering for rev B.

## Reset, boot and debug

- **RESET# (pin 6) → reset supervisor → POR_B.** A TPS3808 (SOT-23-6) watches 3.3 V and holds the chip in reset during power-up, which fixes the missing-POR_B-hold issue on the G2 Nano. The carrier's button drives the supervisor's manual-reset input. **Behaviour change:** on the Teensy, this pin is ON/OFF (hold 5 s to power off). On this card it's a real reset, so SW2's "ON/OFF" label on the carrier becomes "RESET".
- **BOOT# (pin 11) → BOOT_MODE1, and through an SN74LVC1G04 inverter → BOOT_MODE0.**
  - Released: boot mode 10, internal boot from the QSPI flash.
  - Held while pressing reset: boot mode 01, the NXP ROM serial downloader on USB (pins 3/5). The ROM's UART downloader pins (GPIO_AD_24/25) now carry SPI, so on the edge connector the downloader is USB only. That's the standard NXP tool flow (MCUXpresso Secure Provisioning, `blhost`).
  - Using mode 01 explicitly means it still works after fuses are blown for secure boot.
- **BOOT_CFG straps:** 12 × 10k pull-downs (DISP_B1_06–11, DISP_B2_00–05), which select FlexSPI NOR. None of these pads go to the edge connector, so nothing on a carrier can change the boot device.
- **SWD on card test pads** (SWDIO, SWCLK, RESET#, 3.3 V, GND) on the bottom side, sized for a pogo-pin fixture so the same pads serve production programming. MicroMod pins 21/23 now carry SAI4, so SWD is no longer on the edge connector.
- **Status LED** on GPIO_LPSR_08, inside the card. The Teensy's LED is on pin 13 (SCK), which your carrier uses for SPI.

## Clocks and memory

- 24 MHz crystal (2016 size) on XTALI/XTALO, and a 32.768 kHz crystal (3215 size) on RTC_XTALI/O.
- 16 MB GD25Q128EQIGR QSPI NOR on FlexSPI1 port A (the boot ROM's default pins). DQS (SD_B2_05) is left open for loopback sampling.

## Second audio interface (SAI4)

| MicroMod pin | Spec name | RT1176 pad | Ball | Function |
|---|---|---|---|---|
| 13 | RTS1 | GPIO_LPSR_10 | R5 | SAI4_TX_SYNC (AUD2 frame sync) |
| 15 | CTS1 | GPIO_LPSR_09 | P5 | SAI4_TX_DATA (AUD2 out) |
| 21 | SWDCK | GPIO_LPSR_06 | P8 | SAI4_RX_DATA (AUD2 in) |
| 23 | SWDIO | GPIO_LPSR_04 | N7 | SAI4_TX_BCLK (AUD2 bit clock) |

- **Why SAI4:** SAI2 and SAI3 only come out on far-corner EMC_B2 pads. SAI4's pads sit on the right side of the BGA, next to these four fingers. SAI4 supports TDM and runs RX in synchronous mode off its TX clocks, like SAI1 on the codec.
- **No second MCLK on the edge:** there are no spare MicroMod pins left for one. A second codec can share AUD_MCLK (pin 58) if it runs in the same sample-rate family. Otherwise SAI4_MCLK (GPIO_LPSR_05) comes out to a card test pad. A codec whose PLL works from BCLK alone needs no MCLK.
- **Non-standard use of spec pins:** pins 13/15/21/23 are UART flow control and SWD in the MicroMod spec. On a third-party carrier that wires 21/23 to a SWD header, those pins would now carry audio clocks (harmless, but not SWD). On your carrier they're free; label them AUD2_* on rev B.

## Differences from the MicroMod Teensy that affect your carrier or firmware

1. **ADC full scale is 1.8 V, not 3.3 V.** The RT1176's ADC reference tops out at 1.89 V.
   - VIN_SENSE (100k/10k) is fine: about 1.09 V at 12 V, and it clips only above about 18 V.
   - **IGN_SENSE and AUX_SENSE (100k/22k) read about 2.16 V at 12 V, so they clip.** They still work as on/off detection. For real voltage readings, change the divider to 100k/12k on rev B: 1.29 V at 12 V, 1.71 V at 16 V.
2. **RESET is a real reset, not ON/OFF** (see above).
3. **Peripheral instances change:** I2C is LPI2C4, I2C1 is LPI2C1, UART1 is LPUART1, UART2 is LPUART2, SPI is LPSPI2, CAN is FlexCAN2 (the Teensy uses CAN3), PWM0/PWM1 are FlexPWM2, and audio is SAI1 plus SAI4. All RT1176 FlexCANs support CAN FD.
4. **SDIO pins are USDHC1 only.** The Teensy's alternate SPI1 on those pins has no RT1176 equivalent on these pads.
5. **No Teensyduino.** Firmware uses the MCUXpresso SDK or Zephyr. You flash it with the BOOT button over USB, or over SWD through the card's test pads.
6. **The I²C pins (12/14) lose their analog function.** On the Teensy they double as A4/A5; the RT1176's LPI2C1 pads aren't ADC inputs. Every other Teensy analog pin is still on an ADC-capable pad: A0, A1, BATT_VIN/3, G8, G11, and the UART2, I2C1 and audio pins.

## Open items before the schematic

- **DCDC inductor:** NXP asks for 4.7 µH, more than 1.5 A saturation and under 0.1 Ω. No 3 × 3 mm part that meets this is stocked at LCSC. The plan is Sunlord SWPA4030S4R7MT (C57269; 4 × 4 mm, 78 mΩ) in the top-left corner beside the DCDC balls, with the BGA nudged about 0.3 mm right to make room.
- **Flash and card width (decided):** 16 MB **GigaDevice GD25Q128EQIGR** (USON-8, 4 × 4 mm) in the right-hand band, with the card widened **0.8 mm on the pin-1 side, to 22.8 mm**. The 22 mm length, fingers and screw slot are unchanged.
  - Clearance on the rev A.2b carrier: the card bottom sits 2.5 mm above the carrier (Würth 9774025151R standoff). The widened edge stays about 0.25 mm clear of SW2's body (PTS810, 2.5 mm tall). The only part underneath is R137 (0603, not fitted), about 2 mm below the card.
  - The other side can't grow: D22 (SMAJ5.0A, up to 2.44 mm tall) would sit 0.06 mm under the card.
  - Sourcing: the GD25Q128EQIGR isn't stocked at LCSC (DigiKey has it), so it goes through JLC global sourcing or is consigned. Fallbacks: 8 MB W25Q64JVXGIQ (2 × 3 mm, C2940195) fits the same band; 16 MB W25Q128JVPIQ (6 × 5 mm, C190862) needs a rev B carrier with D22/F2 moved.
- Pick LCSC part numbers for every line (stage 2).
- Bottom-side height under the card: the carrier's TE 2199230-4 slot sets how tall bottom parts can be. The 0402s and 0805s are 0.5–1.25 mm, which should be fine; I'll confirm it against the TE drawing.

## Schematic (stage 2)

| Sheet | Contents |
|---|---|
| MicroMod edge, reset, boot, test pads | J1 card edge; U2 TPS3808G30 reset supervisor; U3 SN74LVC1G04 boot inverter; BOOT# pull-up; 3.3 V input bulk; SWD/production test pads TP1–TP7 |
| RT1176 I/O | U1 units: GPIO_AD, LPSR/SNVS/system, SD/DISP, EMC, MIPI. Every pad is labelled with its net or marked no-connect |
| RT1176 power | U1 power unit; L1 DCDC inductor; D1 RTC diode-OR; FB1 (ADC reference), FB2 (ADC 3.3 V); PSWITCH RC; DCDC_MODE and unused-MIPI resistors; all decoupling. Each 0402 cap's Note field names the ball it sits under |
| Flash, clocks, boot straps, LED | U4 GD25Q128EQIGR + pull-ups; Y1 24 MHz; Y2 32.768 kHz; RN1–RN3 BOOT_CFG straps; status LED |

**Checks** (`tools/schcheck.py`, PASS):
- The KiCad netlist matches the design table exactly: 85 parts, 223 nets.
- No single-pin nets, and every power input has a source.
- All 289 RT1176 balls are present.
- Every MicroMod pin matches `pinmap.py`.
- NXP's rail rules hold: grounds, DCDC_IN, VDD_SOC_IN on DCDC_DIG, the 1.8 V analog inputs on DCDC_ANA, NVCC_SNVS tied to VDD_SNVS_ANA, and every NVCC bank at 3.3 V.

KiCad 7's command line has no ERC, so these checks stand in for it. Run ERC in the KiCad 8+ GUI as a cross-check.

**Still open:**
- U4 footprint is done: `rt1176-som:USON-8-1EP_4x4mm_P0.8mm_EP2.3x3mm_GigaDevice`, built from GD25Q128E datasheet DS-00480 rev 1.4 §10.3. The exposed pad goes to GND, which GigaDevice allows.
  - QE (quad enable) ships as 0. The WP#/HOLD# pull-ups keep the part safe in single/dual mode; the boot configuration or firmware must set QE=1 for quad reads.
- L1 footprint: checked. The Changjiang FNR4030S pads (1.1 × 3.7 mm, 1.9 mm gap) match Sunlord's recommended SWPA4030S land pattern exactly. SWPA4030S4R7MT: 78 mΩ max, Isat 2.9 A.
- Choose the 24 MHz crystal (2016 size) and set the C51/C52 load caps from its CL.
- Add LCSC numbers for the passives. Parts with numbers so far: U2 C189211, U3 C7827, L1 C57269, D1 C37704, Y2 C32346.

## Layout (stage 3)

Generated by `tools/pcbgen.py` (placement, BGA fan-out, under-BGA 0402s) and `tools/route.py` (planes, Freerouting, zone fill). Check with `tools/drc.py`.

**Stack-up (6 layers, 0.8 mm):**

| Layer | Use |
|---|---|
| F.Cu | BGA, top parts, odd fingers, signals |
| In1.Cu | GND plane |
| In2.Cu | signals |
| In3.Cu | signals |
| In4.Cu | +3V3 plane, with a DCDC_DIG island from the core balls out to the right-band bulk caps |
| B.Cu | 0402s under the BGA, bottom parts, even fingers, signals |

**Rules:** 0.09 mm track and clearance, 0.3/0.15 mm vias, 0.17 mm copper to hole wall, 0.25 mm hole to hole and copper to edge.

**Fan-out:**
- Balls in the outer two rings that carry signals escape on F.Cu with no via. Every other ball has a dogbone via (0.3/0.15) on the 0.8 mm interstitial grid, and balls on the same rail share vias.
- Decoupling caps sit on the bottom with their pads on those vias (via-in-pad). They need JLC's epoxy-filled, capped vias (POFV), which are standard on 6-layer boards.
- The placer is an integer program: 35 of 39 caps land on vias inside their ball's neighbourhood. The rest, plus the straps and the PSWITCH/DCDC_MODE/MIPI parts, go in free spots and are routed.
- R4, R5 (unused-MIPI pulls) and R9 (BOOT_CFG0) don't fit under the BGA, so they're 0402s on the top side, just outside it.

**Placement notes:**
- The stock courtyards are tightened to the body + 0.15 mm on U1 (the KiCad BGA uses 1 mm), L1 and the test pads. The real body gaps are 0.35 mm (L1 to the BGA) and at least 0.8 mm everywhere else.
- The three 22 µF DCDC_DIG caps (C12, C13, C11) are stacked in the right band so the In3 island can reach all of them.

**Routing:**
- Freerouting could not finish this board (18 nets open at best), and neither could KiCad's interactive router: both lay nets one at a time, and early nets wall off the BGA's bottom rows.
- The signal nets are routed by `tools/nroute`, a negotiated-congestion router written for this card. Nets may overlap at first; shared space gets more expensive each round until every net has its own. It converges in about 20 rounds (under a minute).
- The power rails (DCDC_ANA, SNVS, DCDC_LP/LN, ADC, bulk-cap connections) keep their wider tracks from the Freerouting pass. GND and +3V3 pads in the finger band get a short stub to a new via into the planes.
- Result: 0 unconnected, 0 clearance errors in KiCad 7 DRC. Remaining DRC items are silkscreen overlaps and library-table warnings.
- Inner-layer tracks stay 1.3 mm back from the bevelled finger edge.

Regenerate:

```
python3 tools/pcbgen.py                  # placement + fan-out  -> *-placed.kicad_pcb
python3 tools/nroute/prep.py             # fixed copper -> grid (build/nroute)
g++ -O2 -std=c++17 -o build/nroute/nroute tools/nroute/nroute.cpp
VIA_BASE=24 PRESMUL=1.2 PRESMAX=200 HIST=0.4 build/nroute/nroute build/nroute 250
python3 tools/nroute/emit.py             # tracks + vias -> rt1176-micromod-som.kicad_pcb
python3 tools/drc.py
```

`prep.py` takes the power-rail routing from `docs/layout/power-rails.kicad_pcb` (the last Freerouting result).

**Open layout items:**
- USB1 D+ is 7.2 mm and D− is 10.5 mm, each with two vias, routed as single traces and not as a coupled pair. The 3.3 mm mismatch is about 20 ps, inside the USB 2.0 high-speed skew budget, but the pair should be re-laid side by side.
- The 24 MHz crystal traces are 2.4 mm and 5.2 mm, and XTALO changes layer. Shorten them.
- The plane stubs on the GND and +3V3 fingers are 0.09 mm wide. Widen the two +3V3 ones.
- No GND pour on the signal layers yet.
