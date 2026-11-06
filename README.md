# RT1176 MicroMod SOM

An NXP i.MX RT1176 (Cortex-M7 1 GHz + Cortex-M4 400 MHz) on a MicroMod processor card (M.2 2222 Key E). It uses the SparkFun MicroMod Teensy pinout, so it drops into the RaceLink intercom carrier in place of the MicroMod Teensy.

- **Status:** stage 1 (pin map + floorplan) approved. Stage 2 (schematic) in progress.
- **Design decisions and open items:** [docs/DESIGN.md](docs/DESIGN.md)
- **Pin map:** [docs/PINOUT.md](docs/PINOUT.md). Generated from `tools/pinmap.py`; don't edit by hand.
- **Floorplan:** [docs/floorplan_v0.png](docs/floorplan_v0.png)

## Tools

KiCad 7 + Python, the same toolchain as the intercom carrier.

| Script | Does |
|---|---|
| `tools/pinmap.py` | Single source of truth: MicroMod pin -> RT1176 pad and function |
| `tools/verify.py` | Checks the pin map against NXP's pin-mux data (Zephyr hal_nxp) and the RT1176 ball map: function exists on the pad, no pad used twice, every Teensy pin covered |
| `tools/mktable.py` | Regenerates docs/PINOUT.md |
| `tools/floorplan.py` | Regenerates the floorplan drawing |
