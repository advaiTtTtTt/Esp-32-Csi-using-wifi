# Viva questions and demonstration script

## Likely viva questions

**1. What does CSI stand for?**  
Channel State Information. It describes the wireless channel measured by a receiver for a packet, with values across Wi-Fi subcarriers.

**2. How can Wi-Fi detect movement without a camera?**  
Movement changes the paths taken by radio waves. That can alter the CSI measured at a fixed receiver. We detect sustained changes from a still-room baseline.

**3. Is this a radar in the imaging sense?**  
No. “Radar” describes the sensing demonstration. This prototype reports movement/no movement; the radar graphic is illustrative and does not show a measured position.

**4. Why use CSI instead of RSSI?**  
CSI retains channel information across subcarriers. RSSI reduces a packet to one received-power value, so it has less detail and is more affected by link geometry and interference.

**5. What does the transmitter send?**  
It joins the receiver's SoftAP and sends a small UDP packet every 100 ms. Those packets provide regular frames for CSI measurement.

**6. Why use two ESP32 boards?**  
One makes a predictable stream of Wi-Fi packets and the second measures the received channel. This avoids depending on a home router's CSI behavior.

**7. What is the baseline?**  
Forty still-room samples. We calculate their median and scaled median absolute deviation so a few outliers have limited influence.

**8. Why apply a median filter?**  
It reduces one-sample spikes while preserving abrupt sustained changes better than a long moving average.

**9. How does the movement decision work?**  
The filtered sample's absolute distance from the baseline is compared with a threshold. Three consecutive above-threshold samples start movement; five quiet samples clear it.

**10. What is the sensitivity setting?**  
It multiplies the baseline's robust spread to set the threshold. Lower values respond to smaller changes but may cause more false detections.

**11. What is the RSSI fallback?**  
A receiver mode that records received-power values from data frames when CSI cannot be enabled. It is a lower-detail measurement and should be labeled RSSI in the interface and report.

**12. Can the system identify a person or exact location?**  
No. A single link and a scalar threshold do not support reliable identity, object classification, distance, or room coordinates.

**13. What affects the readings?**  
Board separation and orientation, antenna design, room geometry, Wi-Fi traffic, people moving outside the target path, and board placement.

**14. What does the serial sequence number do?**  
It helps identify ordering or gaps in the receiver's emitted records. The device timestamp is microseconds since boot; the laptop records arrival time for charting.

**15. What was physically tested?**  
State only what you have actually tested. The current project includes software tests and a synthetic dashboard mode; CSI capture and RF performance need the selected boards.

**16. Why are you using the original ESP32-WROOM-32?**  
That is the board available for this project, and ESP-IDF supports CSI on the original ESP32. The firmware is built for the `esp32` target and uses the classic ESP32 CSI configuration. The full demonstration uses two compatible boards, one as transmitter and one as receiver.

## Three-minute evaluator script

**0:00–0:25 — Introduction**  
“This is a Wi-Fi CSI movement detector. A sender transmits periodic Wi-Fi packets, a receiver measures changes in the channel, and a laptop detects sustained changes from a still-room baseline. The display reports coarse movement, not a location.”

**0:25–0:55 — Show the architecture**  
Point to the sender and receiver. Explain the receiver's SoftAP and the serial link to the laptop. State whether the current screen is using demo simulation or physical receiver data.

**0:55–1:25 — Start and calibrate**  
Select the correct source, start monitoring, then press **Calibrate baseline**. Remain still for the 40 sample collection. Point to the calibration message and live graph.

**1:25–1:55 — Still-room observation**  
Remain still and show **NO MOVEMENT**. Explain the median filter, robust spread, and threshold multiplier in one sentence each.

**1:55–2:25 — Movement observation**  
Walk across the signal path. Point out the graph change and **MOVEMENT DETECTED** after persistent deviation. Explain that no position is calculated.

**2:25–2:45 — Session output**  
Show event count, movement time, packet count, signal quality, and download the CSV. If demonstrating simulation, say plainly that these are generated samples.

**2:45–3:00 — Limitations**  
“The detector can have false alarms and needs recalibration after setup changes. RSSI is a weaker fallback. This version does not identify people or show exact locations.”

## Repeatable live test notes

For a hardware result table, record: date/time; ESP32 module markings; ESP-IDF release; board separation; receiver/transmitter placement; 2.4 GHz channel; CSI or RSSI mode; calibration sample count; baseline median/spread; sensitivity; number of prompted movement trials; detected trials; false detections while still; and packets received. Keep simulation data in a separate results row from physical trials.
