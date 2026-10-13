Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
Failed to create stream fd: Operation not permitted
# Wi-Fi Radar

A low-cost, device-free movement detector for a B.Tech wireless technology mini project. A transmitting ESP32 sends small Wi-Fi packets; a receiving ESP32 extracts Channel State Information (CSI) and forwards measurements over USB serial to a Python dashboard. The dashboard calibrates a quiet-room baseline and flags sustained signal changes.

The radar screen is an illustration. This prototype reports movement/no movement and does not estimate direction, distance, identity, or exact position.

## Recommended hardware

The board in your photo is marked **ESP-WROOM-32**, which is the original/classic ESP32. The firmware has been matched to that chip family. This project needs **two compatible original ESP32 boards**: one transmitter and one CSI receiver. If you bought one, you can use it for either role and will need a second ESP32-WROOM-32/DevKit-style board for the other role. The USB connector and exact pin count may vary; use a data-capable cable that fits your board.

Research notes and comparison are in [docs/hardware_research.md](docs/hardware_research.md). Firmware targets the original ESP32 (`esp32`) with ESP-IDF 5.4.4 and uses the classic ESP32 CSI configuration fields.

## System layout

```text
ESP32 transmitter --Wi-Fi packets--> ESP32 receiver / CSI callback
                                             |
                                     USB serial JSON lines
                                             |
                                      Ubuntu laptop
                                             |
                              Python filtering + detector
                                             |
                                   Streamlit dashboard
```

The receiver runs a private Wi-Fi access point (`WIFI_RADAR`, channel 6), so the two-board prototype does not need a home router. Keep the transmitter and receiver about 1–3 m apart with the monitored space between them. The receiver remains connected to the laptop over USB. Power the transmitter from another USB port, charger, or power bank.

## Run the dashboard without hardware

Python 3.10 or later is required. From Ubuntu:

```bash
cd /home/advait/Documents/Codex/2026-10-13/files-pasted-by-the-user-project/outputs/wifi-radar
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run app.py
```

In the sidebar, select **Demo simulation**, choose **CSI amplitude**, click **Start monitoring**, and then **Calibrate baseline**. Remain still during the 40-sample calibration. The simulator periodically creates a marked synthetic movement interval so the dashboard can be demonstrated without radio boards. The active source is always shown in the dashboard.

## Install ESP-IDF and flash the boards

The firmware targets the original ESP32 and ESP-IDF 5.4.4. Install the ESP-IDF toolchain using Espressif's [ESP32 Linux setup guide](https://docs.espressif.com/projects/esp-idf/en/v5.4.4/esp32/get-started/linux-macos-setup.html). A typical installation is:

```bash
sudo apt update
sudo apt install git wget flex bison gperf python3 python3-pip python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0
mkdir -p ~/esp
cd ~/esp
git clone -b v5.4.4 --recursive https://github.com/espressif/esp-idf.git
cd esp-idf
./install.sh esp32
source ./export.sh
```

Keep the ESP-IDF environment activated in each terminal used for firmware commands.

1. Connect the **receiver** to USB and find its port:

   ```bash
   ls -l /dev/serial/by-id/
   ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
   ```

2. Build and flash receiver firmware (replace the port as needed):

   ```bash
   cd /home/advait/Documents/Codex/2026-10-13/files-pasted-by-the-user-project/outputs/wifi-radar/firmware/receiver
   idf.py set-target esp32
   idf.py build
   idf.py -p /dev/ttyUSB0 flash monitor
   ```

   It starts the access point and writes newline-delimited JSON for each CSI measurement. Press `Ctrl+]` to close the serial monitor before opening the dashboard; only one program can own the receiver's serial port at a time.

3. Connect the **transmitter** board, open another terminal with ESP-IDF activated, and flash it:

   ```bash
   cd /home/advait/Documents/Codex/2026-10-13/files-pasted-by-the-user-project/outputs/wifi-radar/firmware/transmitter
   idf.py set-target esp32
   idf.py build
   idf.py -p /dev/ttyUSB1 flash monitor
   ```

   Its serial log should report a connection to the receiver access point. It sends one short UDP packet every 100 ms. The receiver's CSI callback measures the received packets.

4. Stop the transmitter's monitor with `Ctrl+]`. Reconnect the receiver to the laptop if needed, activate the Python virtual environment, and run:

   ```bash
   cd /home/advait/Documents/Codex/2026-10-13/files-pasted-by-the-user-project/outputs/wifi-radar
   source .venv/bin/activate
   streamlit run app.py
   ```

   After installing the project requirements, `python -m serial.tools.list_ports -v` also lists recognized serial ports.

5. Select **ESP32 serial**, enter the receiver's port and `115200` baud, click **Start monitoring**, wait for samples, then click **Calibrate baseline**. Keep the other settings at their defaults for the first demonstration.

The built-in network is WPA2 with example credentials `WIFI_RADAR` / `radarpass`. The transmitter sets a fixed locally administered MAC so the receiver can ignore unrelated Wi-Fi frames. Change the credentials and that MAC in both firmware files before using the boards outside a classroom demo.

## RSSI fallback

If CSI capture fails, rebuild the receiver for RSSI-only sampling:

```bash
cd /home/advait/Documents/Codex/2026-10-13/files-pasted-by-the-user-project/outputs/wifi-radar/firmware/receiver
idf.py menuconfig
```

Enable **Wi-Fi Radar → Build RSSI-only receiver fallback**, save and exit, then run `idf.py build flash`. Select **RSSI** in the dashboard sidebar. RSSI is one received-power number per packet, so it has much less detail than CSI and is more sensitive to distance, orientation, people, and other Wi-Fi traffic. The fallback uses the same original ESP32 target.

## Serial protocol

The receiver emits one UTF-8 JSON object followed by `\n` per measurement. Device time is microseconds since boot; `seq` increments per captured sample.

CSI mode:

```json
{"type":"csi","seq":42,"t_us":4200000,"rssi_dbm":-48,"amplitude":21.531,"csi_bytes":128}
```

RSSI fallback:

```json
{"type":"rssi","seq":42,"t_us":4200000,"rssi_dbm":-48}
```

The amplitude is the RMS magnitude of valid packed I/Q byte pairs across the received CSI buffer. It is a compact motion feature, not a calibrated distance measurement. ESP-IDF log lines may also appear on serial; the dashboard ignores non-JSON lines.

## Signal-processing outline

1. Parse a measurement and reject malformed or non-finite values.
2. Apply a 5-sample trailing median filter to suppress isolated spikes.
3. Calibrate the median and robust spread (scaled median absolute deviation) from 40 still-room samples.
4. Set the change threshold to the greater of `sensitivity × baseline spread` and a small noise floor.
5. Require three consecutive filtered samples beyond the threshold to start movement; require five quiet samples to clear it.

The detector is intentionally explainable. It is a threshold-based motion flag, not a learned classifier. It does not report a probability or confidence score.

## Testing

Run the unit suite from the project directory:

```bash
python -m unittest discover -s tests -v
```

The tests cover robust calibration, median filtering, persistence/release behavior, and serial JSON validation. They do not test RF performance or flashable firmware. The firmware has not been compiled or tested on the purchased board yet.

## Repeatable demonstration

1. Place the receiver and transmitter on opposite sides of the room, about 1–3 m apart.
2. Open the dashboard in demo mode first, or connect the receiver over serial for the physical demonstration.
3. Click **Start monitoring** and wait until the signal graph has a steady stream.
4. Click **Calibrate baseline** and remain still for about four seconds.
5. Stand still for several seconds and show **NO MOVEMENT**.
6. Walk across or between the boards and show the signal change and **MOVEMENT DETECTED** state.
7. Stop, allow the detector to settle, and export the session CSV.

For an evaluator, say clearly whether the data source is the simulator or the ESP32 receiver.

## Troubleshooting

- **No serial port:** use a USB data cable; check `/dev/serial/by-id/` and `python3 -m serial.tools.list_ports -v`. Some boards need CH340/CP210x drivers. Add your Linux account to `dialout` with `sudo usermod -aG dialout "$USER"`, then sign out and back in.
- **Serial permission denied:** close ESP-IDF monitor or any other serial terminal. Only one process can open the receiver port.
- **No packets / receiver says no data:** verify the transmitter is flashed with the transmitter app, both boards use the same SSID/password/channel constants, and the transmitter log says it connected. Power-cycle the receiver before the transmitter.
- **CSI unsupported or no CSI callback samples:** confirm both boards use the original ESP32 (the module marking should say ESP-WROOM-32) and `idf.py set-target esp32` was used. Check that `CONFIG_ESP_WIFI_CSI_ENABLED=y` is present in the receiver `sdkconfig`, flash/start the receiver first, then power on the transmitter, and confirm the transmitter uses the same fixed MAC as the receiver filter. If CSI still fails, select the RSSI-only fallback.
- **RSSI only:** choose **RSSI** in the dashboard. RSSI has lower sensitivity and may need a calmer room or adjusted sensitivity.
- **False movement flags:** increase the sensitivity multiplier, move the boards farther from people walking outside the intended path, reduce nearby Wi-Fi traffic, and recalibrate while the room is still.
- **Dashboard graph is blank:** ensure the selected metric exists in the incoming stream. A fallback stream has RSSI but no CSI amplitude. The sidebar displays a prompt when RSSI-only data arrives while CSI amplitude is selected.
- **Port is not `/dev/ttyUSB0`:** USB bridges can appear as `/dev/ttyACM0` or a stable `/dev/serial/by-id/...` path.

## Files

- `app.py` — Streamlit dashboard and controls.
- `src/data_collector.py` — simulation, serial reader, and JSON parser.
- `src/signal_processing.py` — median filter and robust baseline calculation.
- `src/movement_detector.py` — persistence-based motion state machine.
- `src/visualizations.py` — live signal chart and illustrative radar sweep.
- `firmware/receiver/` — original ESP32 CSI receiver with RSSI-only build option.
- `firmware/transmitter/` — original ESP32 packet transmitter.
- `docs/project_report.md` — academic report.
- `docs/viva_and_demo.md` — likely viva questions and presentation script.
- `docs/hardware_research.md` — board selection and references.
