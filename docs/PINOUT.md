| Pin | MicroMod | Teensy | RT1176 pad | Ball | Function | Notes |
|---|---|---|---|---|---|---|
| 1 | GND |  | GND |  | GND |  |
| 2 | 3.3V |  | +3V3 |  | 3.3 V in from carrier | all I/O banks, DCDC_IN, LPSR_IN at 3.3 V |
| 3 | USB_D+ | USB | USB1_DP | E17 | USB OTG1 D+ | NXP ROM serial downloader runs here |
| 4 | 3.3V_EN | 28 | DISP_B1_05 | C11 | GPIO | Teensy uses it as GPIO 28 |
| 5 | USB_D- | USB | USB1_DN | E16 | USB OTG1 D- |  |
| 6 | RESET# | ON/OFF | POR_B (via reset supervisor) | T10 | reset (via supervisor to POR_B) | Teensy: ONOFF. Here: real reset |
| 7 | GND |  | GND |  | GND |  |
| 8 | G11 | 27/A13 | AD_15 | M14 | GPIO / ADC1_CH4B |  |
| 9 | USB_VIN | VUSB | USB1_VBUS | D17 | USB OTG1 VBUS sense | 5 V tolerant VBUS input |
| 10 | D0 | 4 | EMC_B1_09 | A3 | GPIO / FLEXPWM2_PWM1_B | carrier: PTT1_IN |
| 11 | BOOT# | PROG | LPSR_03 | T7 | BOOT_MODE1 (10k pull-up) + inverter to BOOT_MODE0 | held low at reset = BOOT_MODE 01, USB serial downloader |
| 12 | I2C_SDA | 18/A4 | DISP_B2_13 | A5 | LPI2C4_SDA |  |
| 13 | RTS1 | (NC on Teensy) | LPSR_10 | R5 | SAI4_TX_SYNC | AUD2_LRCLK (second SAI) |
| 14 | I2C_SCL | 19/A5 | DISP_B2_12 | B6 | LPI2C4_SCL |  |
| 15 | CTS1 | (NC on Teensy) | LPSR_09 | P5 | SAI4_TX_DATA | AUD2_OUT (second SAI) |
| 16 | I2C_INT# | 29 | DISP_B1_01 | D13 | GPIO |  |
| 17 | TX1 | 1 | DISP_B1_02 | D11 | LPUART1_TX |  |
| 18 | D1 | 5 | EMC_B1_19 | C4 | GPIO / FLEXPWM2_PWM3_A | carrier: PTT2_IN |
| 19 | RX1 | 0 | DISP_B1_03 | E11 | LPUART1_RX |  |
| 20 | RX2 | 16/A2 | DISP_B2_11 | A6 | LPUART2_RX |  |
| 21 | SWDCK | (NC on Teensy) | LPSR_06 | P8 | SAI4_RX_DATA | AUD2_IN (second SAI); SWD moved to card test pads |
| 22 | TX2 | 17/A3 | DISP_B2_10 | D9 | LPUART2_TX |  |
| 23 | SWDIO | (NC on Teensy) | LPSR_04 | N7 | SAI4_TX_BCLK | AUD2_BCLK (second SAI); SWD moved to card test pads |
| 32 | PWM0 | 3 | AD_28 | L17 | FLEXPWM2_PWM2_A | carrier: CODEC_RST |
| 33 | GND |  | GND |  | GND |  |
| 34 | A0 | 14 | AD_13 | L12 | GPIO / ADC1_CH3B | carrier: IGN_SENSE |
| 35 | USBHOST_D+ | USB2 | USB2_DP | C17 | USB OTG2 D+ |  |
| 36 | GND |  | GND |  | GND |  |
| 37 | USBHOST_D- | USB2 | USB2_DN | C16 | USB OTG2 D- |  |
| 38 | A1 | 15 | AD_19 | L16 | GPIO / ADC2_CH0B | carrier: AUX_SENSE |
| 39 | GND |  | GND |  | GND |  |
| 40 | G0 | 40 | AD_34 | J16 | GPIO | carrier: AMP_MUTE |
| 41 | CAN_RX | 30 | AD_31 | J17 | CAN2_RX | Teensy used CAN3; RT1176 CAN1-3 are all FD |
| 42 | G1 | 41 | AD_32 | K16 | GPIO |  |
| 43 | CAN_TX | 31 | AD_30 | K17 | CAN2_TX |  |
| 44 | G2 | 42 | AD_33 | H17 | GPIO | carrier: ETH_RST |
| 45 | GND |  | GND |  | GND |  |
| 46 | G3 | 43 | AD_18 | M16 | GPIO |  |
| 47 | PWM1 | 2 | AD_29 | M17 | FLEXPWM2_PWM2_B | carrier: CAN_STB |
| 48 | G4 | 44 | AD_04 | M13 | GPIO |  |
| 49 | BATT_VIN/3 | 22/A8 | AD_16 | N17 | GPIO / ADC1_CH5A | carrier: VIN_SENSE |
| 50 | AUD_BCLK | 21 | AD_22 | K12 | SAI1_TX_BCLK | TDM bit clock |
| 51 | I2C_SDA1 | 25/A11 | AD_09 | R16 | LPI2C1_SDA |  |
| 52 | AUD_LRCLK | 20 | AD_23 | J12 | SAI1_TX_SYNC | TDM frame sync |
| 53 | I2C_SCL1 | 24/A10 | AD_08 | R15 | LPI2C1_SCL |  |
| 54 | AUD_IN | 8 | AD_20 | K13 | SAI1_RX_DATA00 | RX in sync mode off TX clocks |
| 55 | SPI_CS# | 10 | AD_25 | M15 | LPSPI2_PCS0 |  |
| 56 | AUD_OUT | 7 | AD_21 | K14 | SAI1_TX_DATA00 |  |
| 57 | SPI_SCK | 13 | AD_24 | L13 | LPSPI2_SCK |  |
| 58 | AUD_MCLK | 23 | AD_17 | N15 | SAI1_MCLK |  |
| 59 | SPI_SDO | 11 | AD_26 | L14 | LPSPI2_SDO |  |
| 60 | SDIO_CLK | 36 | SD_B1_01 | D15 | USDHC1_CLK | Teensy SPI1 alt not available on these pads |
| 61 | SPI_SDI | 12 | AD_27 | N16 | LPSPI2_SDI |  |
| 62 | SDIO_CMD | 37 | SD_B1_00 | B16 | USDHC1_CMD |  |
| 63 | G10 | 33 | AD_03 | P15 | GPIO | carrier: ETH_INT |
| 64 | SDIO_DATA0 | 35 | SD_B1_02 | C15 | USDHC1_DATA0 |  |
| 65 | G9 | 32 | AD_11 | P16 | GPIO | carrier: FP_GPIO2 |
| 66 | SDIO_DATA1 | 34 | SD_B1_03 | B17 | USDHC1_DATA1 |  |
| 67 | G8 | 26/A12 | AD_07 | T17 | GPIO / ADC1_CH0B | carrier: FP_GPIO1 |
| 68 | SDIO_DATA2 | 39 | SD_B1_04 | B15 | USDHC1_DATA2 |  |
| 69 | G7 | 9 | AD_12 | P17 | GPIO | carrier: FP_BOOT |
| 70 | SDIO_DATA3 | 38 | SD_B1_05 | A16 | USDHC1_DATA3 |  |
| 71 | G6 | 6 | AD_01 | R14 | GPIO | carrier: FP_NRST (drive open-drain) |
| 72 | RTC_3V | VBAT | VDD_SNVS_IN | U12 | RTC backup supply (diode-OR with 3.3 V) |  |
| 73 | G5 | 45 | AD_10 | R17 | GPIO | carrier: ETH_CS |
| 74 | 3.3V |  | +3V3 |  | 3.3 V in |  |
| 75 | GND |  | GND |  | GND |  |

Pins 24–31 are the key notch.

### Card-internal pads

| RT1176 pad | Ball | Use |
|---|---|---|
| SD_B2_05 | E14 | FLEXSPI1_A_DQS (leave open: loopback read strobe) |
| SD_B2_06 | F17 | FLEXSPI1_A_SS0_B -> flash CS# |
| SD_B2_07 | G14 | FLEXSPI1_A_SCLK -> flash CLK |
| SD_B2_08 | F15 | FLEXSPI1_A_DATA00 -> flash IO0 |
| SD_B2_09 | H15 | FLEXSPI1_A_DATA01 -> flash IO1 |
| SD_B2_10 | H14 | FLEXSPI1_A_DATA02 -> flash IO2 |
| SD_B2_11 | F16 | FLEXSPI1_A_DATA03 -> flash IO3 |
| LPSR_02 | P6 | BOOT_MODE0 = inverted BOOT# (SN74LVC1G04) |
| LPSR_08 | U8 | status LED (active high, 0603) |
| LPSR_14 | T6 | SWD clock -> test pad |
| LPSR_15 | U7 | SWD data -> test pad |
| LPSR_05 | N8 | SAI4_MCLK -> test pad (optional, not on the edge) |
| DISP_B1_06 | D10 | BOOT_CFG strap (10k pull-down) |
| DISP_B1_07 | E12 | BOOT_CFG strap (10k pull-down) |
| DISP_B1_08 | A15 | BOOT_CFG strap (10k pull-down) |
| DISP_B1_09 | C13 | BOOT_CFG strap (10k pull-down) |
| DISP_B1_10 | B14 | BOOT_CFG strap (10k pull-down) |
| DISP_B1_11 | A14 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_00 | E8 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_01 | F8 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_02 | E9 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_03 | D7 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_04 | C7 | BOOT_CFG strap (10k pull-down) |
| DISP_B2_05 | C9 | BOOT_CFG strap (10k pull-down) |
