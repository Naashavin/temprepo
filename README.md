# Machine_Doc: Virtual Factory Machine Simulator & Raspberry Pi Safety Controller

An end-to-end **Industrial Cyber-Physical Digital Twin** and **Worker Safety Interlock System**.

This project pairs an interactive web-based machine simulator with an edge safety controller running on a **Raspberry Pi 4B** (or locally on your PC). The simulator generates realistic 100 Hz 3-axis vibration kinematics, thermal dynamics, and mechanical load physics, while the Raspberry Pi safety PLC processes real-time telemetry, calculates dynamic vibration RMS, evaluates worker safety zones, and actuates a hardware safety relay to cut motor power during critical conditions.

---

## Deliverables in this Directory

| File | Description |
| :--- | :--- |
| **[`machine_simulator.html`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/machine_simulator.html)** | Self-contained industrial HMI and 100 Hz physics simulation engine. Zero dependencies, no npm, no build step. Opens directly in Google Chrome or Microsoft Edge. |
| **[`pi_receiver.py`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/pi_receiver.py)** | Industrial safety controller and watchdog receiver built with Python Flask. Handles real-time telemetry, dynamic RMS calculation, watchdog timeouts, and physical GPIO relay actuation. |
| **[`README.md`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/README.md)** | Comprehensive operator manual, Raspberry Pi connection guide, hardware wiring guide, and JSON telemetry specifications. |

---

## System Architecture

```text
+---------------------------------------------------------------------------------------+
|                              LAPTOP / PC BROWSER (HMI)                                |
|                                                                                       |
|   +--------------------------+   +-----------------------+   +--------------------+   |
|   |   100 Hz Physics Engine  |   |   Interactive SVG     |   |  Real-Time 5s      |   |
|   |   - Web Worker Blob      |   |   Motor Visualizer    |   |  Oscilloscope      |   |
|   |   - Vibration Kinematics |   |   - Fan / Shaft spin  |   |  - Accel X, Y, Z   |   |
|   |   - Thermal Dynamics     |   |   - Chassis vibration |   |  - Threshold lines |   |
|   +------------+-------------+   +-----------------------+   +--------------------+   |
|                |                                                                      |
|                v Batches of 10 samples (10 Hz / 100 ms) via HTTP POST /data           |
+----------------|----------------------------------------------------------------------+
                 |
                 | Local Wi-Fi / Ethernet Network (JSON over HTTP)
                 v
+----------------|----------------------------------------------------------------------+
|                v                                                                      |
|   +-------------------------------------------------------------------------------+   |
|   |                         RASPBERRY PI 4B (pi_receiver.py)                      |   |
|   |                                                                               |   |
|   |  * Ingests 100 Hz Accel samples (10 samples every 100 ms)                      |   |
|   |  * Computes dynamic RMS (mean-removed, 1-second rolling window)               |   |
|   |  * Evaluates Safety State Machine: RUN / WARNING / FAULT / STOP               |   |
|   |  * 1.0s Link Watchdog Timer: failsafe trip if connection drops                |   |
|   +---------------------------------------+---------------------------------------+   |
|                                           |                                           |
|                                           v Actuates GPIO Pin 18                      |
|                               +-----------------------+                               |
|                               | Physical Safety Relay |                               |
|                               | (Cuts machine power)  |                               |
|                               +-----------------------+                               |
+---------------------------------------------------------------------------------------+
```

---

## 1. What You Can Do With This Project & Simulation

This platform simulates real industrial equipment (such as a 3-phase induction motor, pump, or fan assembly) monitored by an Industry 4.0 safety interlock:

### 1. High-Fidelity Physics & Kinematics Engine
* **100 Hz 3-Axis Accelerometer Generation**: Simulates realistic mechanical vibration across X, Y, and Z axes, incorporating base rotational harmonics, slight shaft eccentricity, Gaussian-like mechanical noise, and a static 1.0 g gravity vector on the Z axis.
* **Mechanical Load & Speed Droop**: Adjust the mechanical load from 0% to 100%. As load increases, the motor undergoes realistic speed droop (up to 80 RPM droop at full load) and elevated baseline vibration.
* **Rotational Inertia & Coast-Down Physics**: When power is cut or stopped, the motor does not stop instantly; it decelerates realistically at 400 RPM/second, taking ~3.75 seconds to coast from 1500 RPM down to a complete halt.
* **Thermal Dynamics**: Models motor stator temperature with realistic heat generation under load, passive ambient convective cooling, and thermal runaway during fault events.

### 2. Live Interactive Industrial HMI Visualizer
* **Animated SVG Motor Graphic**: The motor cooling fan and output drive shaft rotate at speeds mathematically synchronized with current RPM.
* **Proportional Chassis Shaking**: The entire motor SVG visibly vibrates with displacement proportional to real-time vibration amplitude.
* **Industrial Status Lamp**: Displays real-time operational states: `POWER STANDBY` (grey), `MOTOR RUNNING` (pulsing green), and `SAFETY LOCKOUT` (flashing red).

### 3. Multi-Channel Real-Time Oscilloscope
* Plots continuous 5-second waveforms for **Accel X** (cyan), **Accel Y** (purple), and **Accel Z** (gold) on a hardware-accelerated 60 FPS HTML5 canvas.
* Displays dynamic vibration thresholds with horizontal marker lines:
  * **Warning Threshold (0.40 g)** &mdash; Dashed Amber line.
  * **Critical Trip Threshold (0.55 g)** &mdash; Dashed Red line.

### 4. Interactive Fault Injection
Test industrial safety responses in real time with dedicated operator fault triggers:
* **Bearing Fault**: Injects 2nd harmonic impact spikes (impacts occurring at twice rotational speed) and smoothly ramps dynamic vibration amplitude 3&times; to 5&times; over 1.5 seconds.
* **Overheat Fault**: Initiates thermal runaway (+1.5 °C/second) to test warning alarms (60 °C) and emergency thermal shutdowns (75 °C).
* **Worker Zone Intrusion Violation**: Simulates an operator breaching an optical safety light curtain or computer vision exclusion zone, triggering an instantaneous emergency stop.
* **Watchdog Failsafe Trip**: If the network cable is unplugged or the simulator tab is terminated, the Raspberry Pi's internal 1.0-second hardware watchdog trips the safety relay to safe de-energization (`relay=false`).

### 5. Industrial Safety State Machine & Interlocks
The controller evaluates priorities on every telemetry packet:
1. **Worker Intrusion** &rarr; Immediate emergency trip (`relay=false`, `STOP`).
2. **Critical Vibration (&ge; 0.55 g)** &rarr; Emergency trip (`relay=false`, `FAULT`).
3. **Critical Temperature (&ge; 75 °C)** &rarr; Emergency trip (`relay=false`, `FAULT`).
4. **Elevated Warning (RMS &ge; 0.40 g or Temp &ge; 60 °C)** &rarr; Amber alert (`relay=true`, `WARNING`).
5. **Normal Operation** &rarr; Green status (`relay=true`, `RUN`).
6. **Restart Interlock**: When the safety relay trips open, the **START** button is locked out. Operators cannot restart until active faults are cleared.

### 6. Background-Safe Web Worker Execution
Standard browsers throttle background tabs to 1 Hz or pause timers entirely. This simulator spawns an in-memory **Web Worker via a Blob URL** (retaining single-file self-containment) to guarantee steady 100 Hz simulation ticks and 100 ms packet dispatch even when navigating other windows.

---

## 2. Connecting the Raspberry Pi 4B to the Code

Follow these step-by-step instructions to connect your physical Raspberry Pi 4B to the simulator.

### Step 1: Hardware & Network Prerequisites
* **Raspberry Pi 4B** (or 3B+ / Zero 2W) running Raspberry Pi OS (Bookworm or Bullseye).
* **Laptop or PC** running Google Chrome or Microsoft Edge.
* **Local Network**: Both the Raspberry Pi and your laptop must be connected to the **same local network** (same Wi-Fi router, mobile hotspot, or direct Ethernet cable).

### Step 2: Find Your Raspberry Pi's IP Address
On your Raspberry Pi, open a terminal and run:
```bash
hostname -I
```
This will print your Pi's local IP address (for example: `192.168.1.120`).

Alternatively, find its mDNS hostname:
```bash
hostname
```
*(By default, this is `raspberrypi.local`)*.

### Step 3: Transfer `pi_receiver.py` to the Raspberry Pi
Choose one of the following methods to copy `pi_receiver.py` from your laptop to your Raspberry Pi:

* **Method A &mdash; Using SCP (Terminal / PowerShell)**:
  ```powershell
  # Run this on your laptop from the project folder:
  scp pi_receiver.py pi@raspberrypi.local:~/
  # Or use the IP address:
  scp pi_receiver.py pi@192.168.1.120:~/
  ```

* **Method B &mdash; Using a USB Flash Drive**:
  Copy `pi_receiver.py` onto a USB drive, plug it into the Pi, and copy it to your home directory (`/home/pi`).

* **Method C &mdash; Using VS Code Remote SSH**:
  Open VS Code, install the *Remote - SSH* extension, connect to your Raspberry Pi, and drag-and-drop `pi_receiver.py` into the file explorer.

### Step 4: Install Dependencies on the Raspberry Pi
On the Raspberry Pi terminal, ensure Python 3 and Flask are installed:

* **On Raspberry Pi OS (Bookworm)**:
  ```bash
  sudo apt-get update
  sudo apt-get install -y python3-flask
  ```

* **Or using a Python Virtual Environment**:
  ```bash
  python3 -m venv ~/safety_env
  source ~/safety_env/bin/activate
  pip install flask
  ```

### Step 5: Start `pi_receiver.py` on the Raspberry Pi
Run the controller script on the Pi:
```bash
python3 pi_receiver.py
```

You will see the startup banner:
```text
=================================================================
 Raspberry Pi 4B Machine Safety Controller Receiver
 Listening on: http://0.0.0.0:5000/data
 Vibration Thresholds: Warn=0.4g | Crit=0.55g
 Temp Thresholds:      Warn=60.0°C | Crit=75.0°C
 Hardware Relay:      SIMULATION / MOCK
=================================================================
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
```
*(Leave this terminal window running)*.

### Step 6: Verify Endpoint Connectivity from Your Laptop
Before opening the simulator, confirm that your laptop can reach the Pi's server:
1. Open a browser on your laptop.
2. Navigate to:
   ```text
   http://192.168.1.120:5000/
   ```
   *(Replace with your Raspberry Pi's actual IP address or `http://raspberrypi.local:5000/`)*
3. You should see a clean JSON response:
   ```json
   {
     "last_packet_age_s": null,
     "reason": "Awaiting initial packet",
     "relay": true,
     "rms": 0.0,
     "service": "Raspberry Pi Industrial Safety Controller",
     "state": "STOP"
   }
   ```

### Step 7: Connect the Simulator to the Raspberry Pi
1. On your laptop, open [`machine_simulator.html`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/machine_simulator.html) in Chrome or Edge.
2. Locate **Panel 3: Control Panel** on the right side of the screen.
3. Scroll down to the **Raspberry Pi Connection Config** box.
4. In the **Raspberry Pi Network Address** input field, type your Pi's address:
   ```text
   http://192.168.1.120:5000
   ```
   *(or `http://raspberrypi.local:5000`)*
5. Click **Connect** (or press Enter).
6. Verify connection status:
   * The top-right badge switches to **`Pi Link: Connected`** (Green).
   * The **RTT** (round-trip time latency in milliseconds) and **Sent / Recv packet counters** begin incrementing in Panel 4.
   * The address is automatically saved to your browser's `localStorage` so you won't need to re-enter it next time.

---

## 3. Physical Hardware Wiring Guide (Optional Real Peripherals)

`pi_receiver.py` is configured with `ENABLE_REAL_GPIO = False` by default so you can test without physical hardware attached. When you are ready to connect a real relay module or sensors to your Raspberry Pi 4B, configure the hardware hooks:

### 1. Connecting a 5V Safety Relay Module
Controls power to a physical motor or pilot indicator light.

```text
Raspberry Pi 4B Header             5V Relay Module
+--------------------+            +---------------+
| Pin 2  (5V Power)  | ---------> | VCC           |
| Pin 6  (GND)       | ---------> | GND           |
| Pin 12 (GPIO 18)   | ---------> | IN / Signal   |
+--------------------+            +---------------+
```

* Enable physical GPIO in [`pi_receiver.py`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/pi_receiver.py#L30):
  ```python
  ENABLE_REAL_GPIO = True
  RELAY_PIN = 18
  ```
* Install `RPi.GPIO`:
  ```bash
  sudo apt-get install python3-rpi.gpio
  ```

### 2. Peripheral Expansion Pinout Reference

| Peripheral | Component | Pi Interface | Default Pi Pins |
| :--- | :--- | :--- | :--- |
| **Safety Relay** | 1-Channel 5V Relay Module | GPIO Digital Output | GPIO 18 (Physical Pin 12), 5V (Pin 2), GND (Pin 6) |
| **Ambient Temp/Humidity** | DHT22 / AM2302 Sensor | 1-Wire Digital | GPIO 4 (Physical Pin 7), 3.3V (Pin 1), GND (Pin 9) |
| **Gas / Smoke Sensor** | MQ-2 or MQ-135 Sensor | SPI via MCP3008 ADC | SCLK (Pin 23), MISO (Pin 21), MOSI (Pin 19), CE0 (Pin 24) |
| **Zone Intrusion Camera** | Raspberry Pi Camera Module 3 | CSI Ribbon Cable | Dedicated CAM / CSI Port on Raspberry Pi 4B |

Hardware hooks and sample code for Adafruit DHT, MCP3008 SPI ADC, and Picamera2 are pre-written in [`pi_receiver.py:L54-L88`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/pi_receiver.py#L54-L88).

---

## 4. Running the Complete System Locally on Your PC (Without a Pi)

You can run both the Python safety controller and the simulator frontend on the same PC (Windows, macOS, or Linux) with mock GPIO.

1. Open PowerShell or Terminal in this folder:
   ```powershell
   python pi_receiver.py
   ```
2. Open [`machine_simulator.html`](file:///c:/Users/Avinaash.A/OneDrive/Documents/my%20projects/RaspberryPI/machine_simulator.html) in your browser.
3. In Panel 3 under **Raspberry Pi Network Address**, enter:
   ```text
   http://localhost:5000
   ```
   *(or `http://127.0.0.1:5000`)*
4. Click **Connect**. The simulator will stream live data to your local Python process.

---

## 5. How to Work With the Simulation (Operator Manual)

### Overview of HMI Panels

* **Top Header & State Banner**: Displays real-time controller states (**`RUN`**, **`WARNING`**, **`FAULT`**, **`STOP`**), active reason string, and link latency badge.
* **Panel 1: Machine Telemetry & Visualizer**:
  * Rotating fan and shaft SVG synchronized with actual motor RPM.
  * Micro-vibration chassis displacement animation.
  * Real-time readouts for **Motor Speed (RPM)**, **Shaft Frequency (Hz)**, and **Packet Sequence**.
  * **Dynamic Vibration RMS Card**: Color-coded (Grey &rarr; Amber &rarr; Red) indicating current vibration magnitude in `g`.
  * **Temperature Gauge Card**: Live bar and digital readout with warning and critical trip highlights.
  * **Power Indicator Lamp**: Displays `POWER STANDBY`, `MOTOR RUNNING`, or `SAFETY LOCKOUT`.
* **Panel 2: Real-Time Oscilloscope**: Continuous 5-second 60 FPS scrolling canvas plotting 3-axis accelerometer channels against 0.40 g (Warning) and 0.55 g (Critical) thresholds.
* **Panel 3: Control Panel (Operator Station)**:
  * **`▶ START`** and **`■ STOP`** pushbuttons.
  * **Mechanical Load Slider** (0% to 100%).
  * **Fault Injection Buttons**: Bearing Fault, Overheat Fault, Clear All Faults.
  * **Worker in Zone Simulation Toggle**.
  * **Raspberry Pi Network Address Input** and **Connect / Mode Toggle Button**.
* **Panel 4: Hardware Controller & Pi Link Diagnostics**:
  * Displays the controller's verified decision: State, Hardware Relay contact (`CLOSED` / `OPEN`), dynamic RMS computed on the Pi, and safety reason string.
  * Network performance: Link status, RTT latency (ms), sent/received packet counters.
* **Panel 5: Industrial Event Log**: Real-time event audit log recording operator commands, threshold breaches, safety relay trips, and link reconnect events.

---

### Step-by-Step Operational Workflows

#### Workflow A: Normal Start, Load Adjustment & Coast-Down Stop
1. Click **`▶ START`**.
   * The motor ramps smoothly up to nominal ~1500 RPM over ~2 seconds.
   * The SVG fan and output wheel start spinning.
   * The waveform canvas displays 3-axis traces. Baseline dynamic vibration sits safely around ~0.20 g.
2. Drag the **Mechanical Load** slider up to **80%**:
   * Observe realistic speed droop (RPM drops slightly to ~1436 RPM).
   * Base vibration and motor temperature increase slightly under heavy mechanical load.
3. Click **`■ STOP`**:
   * Power is cut. Target speed drops to 0 RPM.
   * **Inertia Coast-Down**: The motor smoothly decelerates at 400 RPM/second, taking **~3.75 seconds** to come to a complete halt.
   * When speed falls below 10 RPM, the banner transitions from `RUN` to `STOP`, and the power lamp switches to `POWER STANDBY`.

#### Workflow B: Testing Bearing Defect Fault & Vibration Trip
1. While the motor is running at ~1500 RPM, click **`Bearing Fault`**.
2. **Warning Phase (0 to 1.5 seconds)**:
   * Vibration amplitude ramps up 3&times; to 5&times; and second harmonics appear on the oscilloscope.
   * Dynamic RMS crosses the **0.40 g Warning threshold**.
   * The status banner turns amber (**`WARNING`**), but the safety relay remains closed to permit monitored operation.
3. **Critical Trip Phase**:
   * Dynamic RMS crosses the **0.55 g Critical threshold**.
   * The controller immediately trips open the safety relay (**`RELAY: OPEN (TRIPPED)`**).
   * The status banner turns red (**`FAULT`**).
   * Motor drive power is cut, and the motor coasts to a halt.
4. Try clicking **`▶ START`**:
   * The start command is rejected: `Cannot START: Safety interlock active (Relay is open)`.
5. Click **`Clear All Faults`**:
   * Fault multipliers return to normal, the safety relay re-energizes, and the machine is ready to restart.

#### Workflow C: Testing Thermal Overheating Shutdown
1. With the motor running, click **`Overheat Fault`**.
2. Watch the **Motor Temp** gauge steadily rise at +1.5 °C/second.
3. At **60.0 °C**: Status banner switches to amber **`WARNING`**.
4. At **75.0 °C**: Safety relay trips open (**`RELAY: OPEN`**), the status banner switches to red **`FAULT`**, power is cut, and the machine coasts down.
5. Click **`Clear All Faults`** to normalize temperature and reset the interlock.

#### Workflow D: Testing Worker Zone Safety Light Curtain Breach
1. With the motor running, toggle **`Simulate Worker in Zone`** to **ON**.
2. Instantaneous trip occurs:
   * Status banner switches to **`STOP`**.
   * Controller reports `EMERGENCY: Worker detected in restricted zone`.
   * Safety relay drops out immediately.
3. Toggle **`Simulate Worker in Zone`** back to **OFF** to clear the safety curtain.

#### Workflow E: Testing Watchdog Fail-Safe (Network Disconnection)
1. While the machine is running and connected to `pi_receiver.py`:
2. Press `Ctrl + C` in the terminal running `pi_receiver.py` to stop the Python process.
3. Within **1.0 second**, the simulator detects connection loss:
   * Panel badge switches to **`Pi Link: Lost`**.
   * System falls back to fail-safe operation.
4. Restart `python3 pi_receiver.py`. The simulator automatically reconnects and normalizes link telemetry within 500 ms.

---

## 6. Communication Protocol & JSON Specification

The simulator streams batches of 10 samples at **10 Hz** (every 100 ms). To eliminate CORS preflight `OPTIONS` delays across origins (e.g. from `file:///` to `http://raspberrypi.local:5000`), the browser sends `POST /data` with `Content-Type: text/plain`.

### Telemetry Packet (Simulator &rarr; Raspberry Pi)
Sent every 100 ms via `POST /data`:
```json
{
  "seq": 1042,
  "t": 1718000000.123,
  "running": true,
  "rpm": 1485,
  "load": 50,
  "accel": [
    [0.0124, -0.0082, 1.1450],
    [0.0130, -0.0075, 1.1520],
    [0.0118, -0.0068, 1.1380],
    [0.0121, -0.0071, 1.1410],
    [0.0125, -0.0080, 1.1480],
    [0.0132, -0.0078, 1.1550],
    [0.0120, -0.0069, 1.1390],
    [0.0123, -0.0073, 1.1430],
    [0.0127, -0.0081, 1.1500],
    [0.0131, -0.0077, 1.1530]
  ],
  "motor_temp": 52.4,
  "worker_in_zone_sim": false
}
```

### Response Packet (Raspberry Pi &rarr; Simulator)
Returned in response to `POST /data`:
```json
{
  "state": "RUN",
  "relay": true,
  "reason": "All normal",
  "rms": 0.212,
  "gas": 0.150,
  "worker_in_zone": false
}
```

---

## 7. Safety Thresholds & Decision Matrix

| Parameter | Normal (Safe) | Warning Alert | Critical Trip Limit | Controller Action on Critical |
| :--- | :--- | :--- | :--- | :--- |
| **Vibration Dynamic RMS** | `< 0.40 g` | `0.40 g – 0.54 g` | `≥ 0.55 g` | De-energize relay (`relay=false`), state=`FAULT` |
| **Motor Temperature** | `< 60.0 °C` | `60.0 °C – 74.9 °C` | `≥ 75.0 °C` | De-energize relay (`relay=false`), state=`FAULT` |
| **Worker Safety Zone** | `Clear (False)` | &mdash; | `Intrusion (True)` | Immediate emergency trip (`relay=false`), state=`STOP` |
| **Network Watchdog** | `< 1.0 s` | &mdash; | `≥ 1.0 s` no packet | Failsafe trip (`relay=false`), state=`FAULT` |

### Dynamic RMS Formula
DC gravity (1.0 g static offset) is eliminated from the rolling 1-second sample window before computing RMS:
$$\bar{z} = \frac{1}{N}\sum_{i=1}^{N} z_i$$
$$\text{RMS}_{\text{dynamic}} = \sqrt{\frac{1}{N}\sum_{i=1}^{N} (z_i - \bar{z})^2}$$

---

## 8. Troubleshooting & Common Questions

### 1. The motor did not turn off immediately when clicking STOP
* In real industrial machines, high-inertia motors have momentum and coast down smoothly.
* The simulator decelerates at **400 RPM/second**. From 1500 RPM, it takes **~3.75 seconds** to reach a complete stop.
* During deceleration, the status banner remains `RUN` until speed drops below 10 RPM, at which point it switches to `STOP`.

### 2. The START button shows "Interlock Active" and will not start
* This indicates that a fault was injected (Bearing Fault, Overheat, or Worker Intrusion) and the safety relay is tripped open.
* Click **`Clear All Faults`** in Panel 3 to reset the interlock, re-energize the relay, and allow starting.

### 3. The badge says "Pi Link: Lost"
* Ensure `pi_receiver.py` is actively running on the target machine.
* Check that both devices are on the same Wi-Fi/subnet. If using public or university Wi-Fi, client-to-client isolation may prevent devices from communicating; use a home router, Ethernet cable, or a mobile hotspot.
* Verify your Pi's IP address by opening `http://<PI_IP>:5000/` directly in a browser tab.
* Check Windows Firewall: ensure Python is permitted to accept incoming connections on port 5000.

### 4. Animation freezes when switching tabs
* Modern web browsers throttle `requestAnimationFrame` to 1 Hz or freeze canvas drawing when a tab is minimized.
* The underlying physics and network dispatch continue unthrottled in the background via the **Web Worker**. Keep the tab visible in the foreground to view the animations at 60 FPS.
