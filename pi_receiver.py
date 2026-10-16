#!/usr/bin/env python3
"""
Machine_Doc: Raspberry Pi 4B Machine Safety Controller & Receiver
=================================================================
Part of the Worker-Safety System.

Receives 100 Hz vibration telemetry & status from machine_simulator.html,
computes dynamic vibration RMS (mean-removed, 1-second window),
monitors temperature, gas levels, and worker safety zones,
and commands the physical safety relay (RUN / WARNING / STOP).

Run on Raspberry Pi 4B:
    python3 pi_receiver.py
"""

import sys
import json
import math
import time
from collections import deque
from threading import Lock, Thread
from flask import Flask, request, jsonify, make_response

# ---------------------------------------------------------------------------
# HARDWARE EXPANSION HOOKS (Raspberry Pi 4B)
# ---------------------------------------------------------------------------
# The flags below allow running in simulation/mock mode on a PC or Pi without
# attached hardware, while providing clear placeholders for real peripherals.

ENABLE_REAL_GPIO = False  # Set to True when running on physical Raspberry Pi with relay

if ENABLE_REAL_GPIO:
    try:
        import RPi.GPIO as GPIO
        RELAY_PIN = 18  # BCM pin 18 (Active LOW or HIGH depending on relay module)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(RELAY_PIN, GPIO.OUT, initial=GPIO.LOW)
    except ImportError:
        print("[WARN] RPi.GPIO not available, falling back to mock GPIO.")
        ENABLE_REAL_GPIO = False

def set_hardware_relay(energized: bool):
    """
    Controls the physical safety relay connected to the Raspberry Pi.
    Energized (True)  -> Relay NC/NO contacts closed (Machine has power)
    De-energized (False) -> Relay tripped open (Machine power cut immediately)
    """
    if ENABLE_REAL_GPIO:
        # Standard active-high or active-low relay board (adjust logic as needed)
        GPIO.output(RELAY_PIN, GPIO.HIGH if energized else GPIO.LOW)
    # Mock log
    # print(f"[RELAY] State: {'ENERGIZED (ON)' if energized else 'TRIPPED (OFF)'}")

def read_dht22_sensor():
    """
    [HARDWARE HOOK] DHT22 Temperature & Humidity Sensor
    Example implementation:
        import adafruit_dht
        import board
        dht_device = adafruit_dht.DHT22(board.D4)
        return dht_device.temperature, dht_device.humidity
    """
    return None, None

def read_mcp3008_gas_sensor():
    """
    [HARDWARE HOOK] MCP3008 8-channel 10-bit SPI ADC for MQ-2 / MQ-135 gas sensor
    Example implementation:
        import busio
        import digitalio
        import board
        import adafruit_mcp3xxx.mcp3008 as MCP
        from adafruit_mcp3xxx.analog_in import AnalogIn
        spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
        cs = digitalio.DigitalInOut(board.D5)
        mcp = MCP.MCP3008(spi, cs)
        channel = AnalogIn(mcp, MCP.P0)
        return channel.voltage / 3.3  # Normalized 0.0 - 1.0
    """
    return 0.15  # Nominal baseline gas reading

def read_camera_worker_zone():
    """
    [HARDWARE HOOK] Real-time camera worker detection (Picamera2 + OpenCV / YOLO)
    Returns True if a worker is detected within the restricted safety zone.
    """
    return False

# ---------------------------------------------------------------------------
# SAFETY THRESHOLDS & CONFIGURATION
# ---------------------------------------------------------------------------
CONFIG = {
    "WARN_RMS_G": 0.40,        # Vibration warning threshold in g
    "CRIT_RMS_G": 0.55,        # Vibration emergency trip threshold in g
    "WARN_TEMP_C": 60.0,       # Motor temperature warning threshold in °C
    "CRIT_TEMP_C": 75.0,       # Motor temperature emergency trip in °C
    "WATCHDOG_TIMEOUT_S": 1.0, # Timeout without packets before FAULT / Relay trip
    "RMS_WINDOW_SAMPLES": 100, # 1-second rolling window at 100 Hz
    "HOST": "0.0.0.0",
    "PORT": 5000
}

# ---------------------------------------------------------------------------
# CONTROLLER STATE & SYNCHRONIZATION
# ---------------------------------------------------------------------------
class SafetyController:
    def __init__(self):
        self.lock = Lock()
        self.last_packet_time = 0.0
        self.sample_history = deque(maxlen=CONFIG["RMS_WINDOW_SAMPLES"]) # deque of [ax, ay, az]
        
        # Current controller decisions
        self.state = "STOP"          # "RUN", "WARNING", "STOP", "FAULT"
        self.relay = True            # True = energized (safe), False = de-energized (cut)
        self.reason = "Awaiting initial packet"
        self.rms = 0.0
        self.gas = 0.15
        self.worker_in_zone = False

    def process_telemetry(self, packet: dict) -> dict:
        now = time.time()
        with self.lock:
            self.last_packet_time = now
            
            # 1. Ingest 100 Hz accelerometer samples from batch
            accel_samples = packet.get("accel", [])
            for s in accel_samples:
                if isinstance(s, (list, tuple)) and len(s) >= 3:
                    self.sample_history.append((float(s[0]), float(s[1]), float(s[2])))

            # 2. Compute dynamic Vibration RMS (mean removed, 1-second window)
            self.rms = self._calculate_dynamic_rms()

            # 3. Read telemetry fields
            running = bool(packet.get("running", False))
            motor_temp = float(packet.get("motor_temp", 30.0))
            worker_sim = bool(packet.get("worker_in_zone_sim", False))
            
            # Combine simulated camera flag with hardware camera hook
            self.worker_in_zone = worker_sim or read_camera_worker_zone()
            
            # Read gas sensor (MCP3008 ADC or baseline)
            self.gas = round(read_mcp3008_gas_sensor(), 3)

            # 4. SAFETY STATE MACHINE EVALUATION
            # Priority 1: Worker safety zone intrusion -> IMMEDIATE STOP / RELAY TRIP
            if self.worker_in_zone:
                self.state = "STOP"
                self.relay = False
                self.reason = "EMERGENCY: Worker detected in restricted zone"

            # Priority 2: Critical mechanical vibration (> 0.55g) -> IMMEDIATE TRIP
            elif self.rms >= CONFIG["CRIT_RMS_G"]:
                self.state = "STOP"
                self.relay = False
                self.reason = f"CRITICAL: Vibration RMS ({self.rms:.2f}g) exceeds limit ({CONFIG['CRIT_RMS_G']:.2f}g)"

            # Priority 3: Critical motor overheating (> 75°C) -> IMMEDIATE TRIP
            elif motor_temp >= CONFIG["CRIT_TEMP_C"]:
                self.state = "STOP"
                self.relay = False
                self.reason = f"CRITICAL: Motor temperature ({motor_temp:.1f}°C) exceeds limit ({CONFIG['CRIT_TEMP_C']:.1f}°C)"

            # Priority 4: Warning level vibration (0.40g - 0.55g) -> WARNING, relay stays energized
            elif self.rms >= CONFIG["WARN_RMS_G"]:
                self.state = "WARNING"
                self.relay = True
                self.reason = f"WARNING: Vibration RMS ({self.rms:.2f}g) elevated"

            # Priority 5: Warning level temperature (60°C - 75°C) -> WARNING, relay stays energized
            elif motor_temp >= CONFIG["WARN_TEMP_C"]:
                self.state = "WARNING"
                self.relay = True
                self.reason = f"WARNING: Motor temperature ({motor_temp:.1f}°C) elevated"

            # Priority 6: Machine Running normally
            elif running:
                self.state = "RUN"
                self.relay = True
                self.reason = "All normal"

            # Priority 7: Machine Stopped normally
            else:
                self.state = "STOP"
                self.relay = True
                self.reason = "Machine stopped normally"

            # Update physical relay
            set_hardware_relay(self.relay)

            return {
                "state": self.state,
                "relay": self.relay,
                "reason": self.reason,
                "rms": round(self.rms, 3),
                "gas": self.gas,
                "worker_in_zone": self.worker_in_zone
            }

    def _calculate_dynamic_rms(self) -> float:
        """
        Calculates Root-Mean-Square (RMS) of dynamic vibration.
        Removes DC component (gravity / mean) first from Z-axis:
        RMS = sqrt( mean( (z - mean_z)^2 ) )
        """
        n = len(self.sample_history)
        if n == 0:
            return 0.0

        # Mean of Z axis
        mean_z = sum(s[2] for s in self.sample_history) / n

        # Sum of squared dynamic deviations
        sum_sq = sum((s[2] - mean_z) ** 2 for s in self.sample_history)
        return math.sqrt(sum_sq / n)

    def check_watchdog(self):
        """
        Watchdog: If no packet has been received within WATCHDOG_TIMEOUT_S (1.0s),
        treat simulator as disconnected / crashed -> Trip safety relay!
        """
        now = time.time()
        with self.lock:
            if self.last_packet_time > 0 and (now - self.last_packet_time) > CONFIG["WATCHDOG_TIMEOUT_S"]:
                if self.relay or self.state != "FAULT":
                    print(f"[WATCHDOG] Link timeout ({now - self.last_packet_time:.2f}s > 1.0s). Tripping safety relay!")
                    self.state = "FAULT"
                    self.relay = False
                    self.reason = "FAULT: Watchdog timeout - Simulator link lost (>1.0s)"
                    set_hardware_relay(False)

controller = SafetyController()

# ---------------------------------------------------------------------------
# WATCHDOG BACKGROUND THREAD
# ---------------------------------------------------------------------------
def watchdog_loop():
    while True:
        time.sleep(0.2)
        controller.check_watchdog()

# Start background watchdog daemon
watchdog_thread = Thread(target=watchdog_loop, daemon=True)
watchdog_thread.start()

# ---------------------------------------------------------------------------
# FLASK WEB SERVER & CORS HANDLER
# ---------------------------------------------------------------------------
app = Flask(__name__)

def add_cors_headers(response):
    """
    Enables CORS on all responses so browsers opening machine_simulator.html
    from file:/// or local network can communicate without security blocks.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept"
    return response

@app.after_request
def after_request_func(response):
    return add_cors_headers(response)

@app.route("/data", methods=["POST", "OPTIONS"])
def data_endpoint():
    # Handle preflight OPTIONS if sent by any client
    if request.method == "OPTIONS":
        resp = make_response()
        return add_cors_headers(resp)

    try:
        # Parse raw payload (supports both Content-Type: text/plain and application/json)
        raw_body = request.get_data(as_text=True)
        if not raw_body:
            return jsonify({"error": "Empty body"}), 400
        
        payload = json.loads(raw_body)
    except Exception as e:
        return jsonify({"error": f"Invalid JSON payload: {str(e)}"}), 400

    # Process through safety controller
    reply = controller.process_telemetry(payload)
    return jsonify(reply), 200

@app.route("/", methods=["GET"])
def index_endpoint():
    """Simple status check endpoint."""
    with controller.lock:
        return jsonify({
            "service": "Machine_Doc Industrial Safety Controller",
            "state": controller.state,
            "relay": controller.relay,
            "reason": controller.reason,
            "rms": round(controller.rms, 3),
            "last_packet_age_s": round(time.time() - controller.last_packet_time, 2) if controller.last_packet_time > 0 else None
        })

# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print(" Machine_Doc: Raspberry Pi 4B Safety Controller Receiver")
    print(f" Listening on: http://{CONFIG['HOST']}:{CONFIG['PORT']}/data")
    print(f" Vibration Thresholds: Warn={CONFIG['WARN_RMS_G']}g | Crit={CONFIG['CRIT_RMS_G']}g")
    print(f" Temp Thresholds:      Warn={CONFIG['WARN_TEMP_C']}°C | Crit={CONFIG['CRIT_TEMP_C']}°C")
    print(f" Hardware Relay:      {'ENABLED' if ENABLE_REAL_GPIO else 'SIMULATION / MOCK'}")
    print("=" * 65)

    try:
        app.run(host=CONFIG["HOST"], port=CONFIG["PORT"], threaded=True)
    finally:
        if ENABLE_REAL_GPIO:
            GPIO.cleanup()
