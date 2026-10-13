# Hardware choice and feasibility

## Selected board

The board in the user's photo has a radio module marked **ESP-WROOM-32**. That is the original/classic ESP32 family, so the firmware now targets ESP-IDF's `esp32` target. The receiver uses the original ESP32 CSI fields (`lltf_en`, `htltf_en`, and related settings); the earlier ESP32-C6-specific configuration has been removed.

This project needs two boards from the original ESP32 family. Use the purchased WROOM-32 board for either the transmitter or receiver and add a second compatible ESP32-WROOM-32 development board for the other role. The exact carrier-board pin count or USB connector does not affect this firmware because it uses Wi-Fi and USB serial, not GPIO sensors. Use a USB data cable that matches the board connector.

## What I compared

| Candidate | Evidence and trade-off | Decision |
| --- | --- | --- |
| **ESP-WROOM-32 / original ESP32 DevKit-style board** | The user already owns one. ESP-IDF 5.4 documents CSI support and the classic CSI data layout. Widely available and inexpensive. | **Selected:** adapt firmware and setup for the photographed board; add one more compatible board for the second endpoint. |
| ESP32-C6-DevKitC-1 | Espressif's current CSI starter guide recommends C5/C6 and provides a C6-specific configuration. It requires different CSI structure fields and is unnecessary now that a classic ESP32 is owned. | Not used by this project version. |
| ESP32-S3 DevKit | Community projects report CSI experiments with S3 boards, but the firmware would require target-specific configuration and a separate compatibility check. | Not selected. |
| RSSI-only sensing | Provides received power per packet rather than CSI's subcarrier values; results are more affected by link geometry and interference. | Kept as a labeled fallback build option. |

An Indian vendor listing for a 30-pin ESP32 DevKit V1 based on ESP32-WROOM-32 showed ₹549 when checked on 13 October 2026. Use that only as a rough estimate for the second board; confirm the module label and connector before ordering. The photographed board already covers one position in the pair.

## Why two boards and a private access point

One board runs as a transmitter and sends a short UDP packet every 100 ms. The other creates a private Wi-Fi access point, receives those frames, extracts CSI, and sends measurements to the laptop by USB serial. The demo does not depend on a home router or cloud service. Start the receiver first so CSI is enabled before the transmitter begins sending.

The transmitter uses a fixed locally administered MAC address. The receiver compares the MAC in each CSI record and drops unrelated frames before sending measurements to the dashboard. Both firmware images must use the same MAC, SSID, password, and channel.

## CSI and sensing limits

- ESP-IDF's original ESP32 CSI guide describes each sample as signed-byte pairs, imaginary first and real second. If `first_word_invalid` is set, the first four bytes are skipped. The firmware reduces the valid pairs to one RMS amplitude value per frame.
- The CSI callback runs in the Wi-Fi task. It performs a short amplitude calculation and queues a record; a separate FreeRTOS task prints serial JSON.
- The receiver enables promiscuous/sniffer mode so it can collect CSI for packets from the transmitter. The MAC filter keeps the dashboard stream tied to this project's sender.
- Espressif's CSI guide recommends enabling sniffer mode for more CSI data. Start with the boards 1–3 m apart and try different orientations if movement does not cause a stable change.
- Motion can change multipath and CSI. A still-room baseline and persistence threshold make a useful classroom motion detector. This is not an imaging radar and does not produce distance, identity, direction, or exact position.
- Firmware compilation and physical CSI performance have not yet been verified on the purchased board.

## Estimated bill of materials (India)

| Item | Qty | Approx. unit price | Approx. total | Notes |
| --- | ---: | ---: | ---: | --- |
| ESP32-WROOM-32 DevKit-style board | 2 | ₹549 | ₹1,098 | One is already purchased; add a second compatible board. |
| USB data cables | 2 | Depends on connector | If owned, ₹0 | The photo shows USB-C; check the other board's connector. |
| Ubuntu laptop | 1 | Already listed | ₹0 | Runs the dashboard and serial connection. |
| Wi-Fi router | 0 | Not required | ₹0 | Receiver SoftAP supplies the link. |

Price snapshot: [TecnoMate's ESP32 DevKit V1 30-pin WROOM-32 listing](https://www.tecnomate.in/component-library/esp32-devkit-v1-wifi-bluetooth-development-board-wroom-32-30-pin) showed ₹549, inclusive of taxes, when checked on 13 October 2026. Prices and stock can change.

## Technical references and project survey

1. Espressif, [ESP-IDF v5.4.4 ESP32 Wi-Fi API](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32/api-reference/network/esp_wifi.html) — target-specific Wi-Fi and CSI APIs.
2. Espressif, [ESP-IDF v5.4.4 ESP32 CSI guide](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32/api-guides/wifi.html) — original ESP32 I/Q ordering, invalid first word, callback context, and sniffer-mode guidance.
3. Espressif, [`esp-csi` getting-started guide](https://github.com/espressif/esp-csi/blob/master/examples/get-started/README.md) — sender/receiver architecture and current C5/C6 recommendation; its current example configuration is not the configuration used for this original ESP32 build.
4. Espressif, [`esp-csi` repository](https://github.com/espressif/esp-csi) — device-to-device and router-based capture examples, parsing tools, and human-activity examples.
5. Espressif, [original ESP32 CSI callback issue #247](https://github.com/espressif/esp-csi/issues/247) — issue report limited to ESP-IDF 5.5.1/5.5.2 traffic-order cases; it does not establish a failure with this project's ESP-IDF 5.4.4 startup sequence.
6. ErfanDL, [WaveSight repository](https://github.com/ErfanDL/WaveSight) — a separate CSI project whose README reports an S3 DevKitC setup and ESP-IDF 5.4.4; treated as a community example, not validation of this firmware.
7. Community context: [r/esp32 CSI presence project using XIAO ESP32 boards](https://www.reddit.com/r/esp32/comments/1qe4qk8/espcsi_diy_wifi_human_presence_detection/) and [r/esp32 discussion of the Espressif CSI setup](https://www.reddit.com/r/esp32/comments/yn1k6e/just_experimenting_with_esp_csi_human_presence/). These are reports of experiments and setup issues, not specifications or controlled performance tests.
8. Board cost reference: [TecnoMate ESP32-WROOM-32 DevKit V1 listing](https://www.tecnomate.in/component-library/esp32-devkit-v1-wifi-bluetooth-development-board-wroom-32-30-pin).

Espressif's documentation and reference projects are the strongest sources for CSI support and data layout. Community projects are useful for seeing experimental approaches, but do not guarantee comparable detection results. This project keeps its signal processing and visualization local on the laptop.
