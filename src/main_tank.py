"""
Tank Level Measurement System
Measures oil tank level via HC-SR04 ultrasonic sensor
Supports ESP32 and Raspberry Pi Pico
"""

import time
import network
import ntptime
import machine
import gc
import os
import sys
from machine import Pin, WDT

# Use ujson for MicroPython (more efficient than standard json)
try:
    import ujson as json
except ImportError:
    import json

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import umqtt.simple as mqtt
except ImportError:
    mqtt = None

try:
    from microdot import Microdot, Response, Request
except ImportError:
    print("ERROR: Microdot not found!")
    raise

from env import *

try:
    from ds18x20 import DS18X20
    from onewire import OneWire
except ImportError:
    DS18X20 = None
    OneWire = None


try:
    from esp32 import wake_on_ext0
except ImportError:
    wake_on_ext0 = None

# Detect platform
try:
    from pf_esp32 import *
    PLATFORM = "ESP32"
except ImportError:
    try:
        from pf_rpi import *
        PLATFORM = "RPI_PICO"        
    except ImportError:
        print("ERROR: No platform file!")
        raise


#MQTT_SERVER = "your-server" (use env.py instead!)
ntptime.host = "192.53.103.104"
Request.max_content_length = 256 * 1024
Request.max_body_length = 2 * 1024

# Global state for restart
launch_restart_pending = False


# Temperature sensors, sorted by name when returned
temp_id_to_name={ "device": "device", "d6" : "1-AUS", "5a" : "2-ABV", "2b" : "3-ABR", "89" : "4-NBV", "49": "5-NBR"}


# Wakeup each minutes, relative to the last full hour
TIMEOUT_REPORT_WAKEUP=60*60
# T_aus determines the wakeup time
T_aus=0
# Temperatures for different wakeup times in 1/10 Celsius
TEMP_15MIN_WAKEUP=30
TIMEOUT_15MIN_WAKEUP=15*60

TEMP_5MIN_WAKEUP=-80
TIMEOUT_5MIN_WAKEUP=5*60

ALARM_TEMP_THRESHOLD_HIGH=250
ALARM_TEMP_THRESHOLD_AUS=40       
ALARM_TEMP_THRESHOLD_LOW=170        

LOGFILE="/log.csv"
# Import stubs here to allow overriding of constants
#from stubs import *

def median(values):
    """Return median of values"""
    if not values:
        return 0
    sorted_vals = sorted(values)
    return sorted_vals[len(sorted_vals) // 2]


def get_memory_usage():
    """Get memory usage statistics"""
    try:
        gc.collect()
        mem_free = gc.mem_free()
        mem_alloc = gc.mem_alloc()
        mem_total = mem_free + mem_alloc

        if mem_total > 0:
            percent_used = (mem_alloc * 100) // mem_total
        else:
            percent_used = 0

        used_kb = mem_alloc // 1024
        total_kb = mem_total // 1024
        return f"{used_kb}KB / {total_kb}KB ({percent_used}%)"
    except Exception as e:
        return f"Error: {e}"


# async def measure_vbus_voltage():
#     """Measure VBUS voltage on ESP32 (async)

#     Uses ADC2 channel 8 (GPIO4) which is connected to VBUS
#     Returns voltage in mV (0-5500 mV typical for USB)
#     Returns -1 if measurement fails
#     """
#     try:
#         from machine import ADC

#         # ESP32 VBUS is typically on ADC2_CH8 (GPIO4)
#         # Voltage divider: VBUS/2 to allow 5V input on 3.3V ADC
#         # Formula: VBUS_mV = (ADC_reading / 4095) * 3300 * 2
#         adc = ADC(machine.Pin(4))
#         adc.atten(ADC.ATTN_11DB)  # 0-3.6V range
#         adc.width(ADC.WIDTH_12BIT)  # 12-bit resolution (0-4095)

#         # Take multiple readings for stability
#         readings = []
#         for _ in range(5):
#             reading = adc.read()
#             # Convert ADC reading to VBUS voltage in mV
#             # With voltage divider (VBUS/2): actual_voltage = (adc_reading / 4095) * 3300 * 2
#             vbus_mv = (reading * 3300 * 2) // 4095
#             readings.append(vbus_mv)
#             await asyncio.sleep_ms(10)

#         # Return median to filter noise
#         vbus_mv = median(readings)
#         print(f"  VBUS: {vbus_mv} mV ({vbus_mv/1000:.2f}V)")
#         return vbus_mv

#     except Exception as e:
#         print(f"  VBUS measurement error: {e}")
        return -1


def measure_distance_mm():
    """Measure distance using HC-SR04"""
    trigger = Pin(SR04_TRIGGER_PIN, Pin.OUT)
    echo = Pin(SR04_ECHO_PIN, Pin.IN)

    trigger.off()
    time.sleep_us(2)
    trigger.on()
    time.sleep_us(10)
    trigger.off()
    
    timeout = 30000
    start = time.ticks_us()
    pulse_start=start
    pulse_end=start
    
    while echo.value() == 0:
        if time.ticks_diff(time.ticks_us(), start) > timeout:
            return -1
        pulse_start = time.ticks_us()
    
    while echo.value() == 1:
        if time.ticks_diff(time.ticks_us(), start) > timeout:
            return -1
        pulse_end = time.ticks_us()
    
    pulse_duration = time.ticks_diff(pulse_end, pulse_start)
    distance = int((pulse_duration * 0.343) / 2)
    
    return distance


def activate_sr04_module(activate=True):    
    power_pin = Pin(SR04_PWR_OUT, Pin.OUT)
    if activate:
        power_pin.on()
    else:
        power_pin.off()


def activate_temp_module(activate=True):    
    power_pin = Pin(DS18B20_PWR, Pin.OUT)
    if activate:
        power_pin.on()
    else:
        power_pin.off()


async def measure_temperatures():
    """Measure temperature from ESP32 internal sensor + up to 5 DS18B20 sensors

    Returns:
        list: List of tuples (sensor_id, temp_int) where sensor_id is identifier
              and temp_int is temperature in °C * 10
    """
    readings = []

    # ESP32 internal temperature sensor (first)
    if PLATFORM == "ESP32":
        try:
            import esp32
            # esp32.raw_temperature() returns raw ADC value, convert to Celsius
            # Formula: T = (raw_value - 32) / 165 * 100 - 40 (approximately)
            raw_temp = esp32.raw_temperature()
            # Simpler conversion that works for ESP32
            temp_c = (raw_temp - 32) / 1.8
            temp_int = int(temp_c * 10)
            readings.append(("device", temp_int))
            print(f"  ESP32 device: {temp_c:.1f}°C ({temp_int}) [raw={raw_temp}]")
        except Exception as e:
            print(f"  ESP32 device sensor: Error - {e}")

    # DS18B20 sensors on 1-Wire bus (up to 4 remaining)
    if DS18X20 is None or OneWire is None:
        if not readings:
            print("WARNING: DS18X20/OneWire modules not available")
        return readings
        
    try:
        # Create 1-Wire bus on single pin
        ow = OneWire(Pin(DS18B20_BUS))
        ds = DS18X20(ow)

        # Scan for connected devices
        devices = ow.scan()
        if not devices:        
            print("No DS18B20 sensors found")
            return readings

        # Convert to list and limit to 5 sensors (1st is ESP32 internal)
        sensor_ids = list(devices)[:5]
        print(f"Found {len(sensor_ids)} DS18B20 sensor(s)")

        # Trigger temperature conversion on all devices
        ds.convert_temp()

        # Read temperatures              
        for i, rom in enumerate(sensor_ids):
            try:
                temp_c = ds.read_temp(rom)
                # Convert to integer (°C * 10) to preserve one decimal place
                temp_int = int(temp_c * 10)
                # Convert ROM (bytes) to hex string (48-bit address)
                rom_hex = rom.hex() if hasattr(rom, 'hex') else ''.join(f'{b:02x}' for b in rom)
                rom_crc=rom_hex[-2:]
                if rom_crc in temp_id_to_name:
                    rom_hex=temp_id_to_name[rom_crc]
                readings.append((rom_hex, temp_int))
                print(f"  DS18B20 {i+1} ({rom_hex}): {temp_c:.1f}°C ({temp_int})")
            except Exception as e:
                print(f"  DS18B20 {i+1}: Error - {e}")
            await asyncio.sleep_ms(0)

        return sorted(readings)
    except Exception as e:
        print(f"✗ Temperature measurement error: {e}")
        return readings    


def convert_dist(dist_mm):
    """Convert distances to normalized values (user fills this), last element is liter.
       Currently, filling levels, i.e. air gap, in mm from top to oil level are reported. Liter is set to 1 wthout any meaning.
    """
    return dist_mm+[1]

class TankMonitor:    

    def __init__(self):
        """Initialize the tank monitoring system"""
        self.wdt = WDT(timeout=15000)
        self.wlan = network.WLAN(network.STA_IF)
        self.app = Microdot()
        self.mqtt_client = None
        self.web_mode_active = False
        self.web_server_running = False
        self.current_datetime_str = "01.01.2000 00:00:00"
        self.last_measurement_time = "01.01.2000 00:00:00"
        self.distance_measurements = [0,0,0]
        self.temperature_readings = []
        #self.vbus_voltage = 0
        self.key_press_time = 0
        self.key_pressed = False
        self.key_released = False
        self.key_pressed_at_startup = False
        self.last_web_request_time = 0
    
        
        """Monitor KEY button"""
        self.key_pin = Pin(KEY_GPIO_IN, Pin.IN, Pin.PULL_UP)
        self.key_pin.irq(trigger=Pin.IRQ_FALLING)

        # Onboard LED for web mode indication (GPIO2 on ESP32)
        self.status_led = Pin(2, Pin.OUT)
        self.status_led.off()

        # Enable watchdog timer        
        #print("✓ Watchdog enabled (15s timeout)")

        # ESP32: Configure external wakeup from deep sleep (active LOW)
        if PLATFORM == "ESP32" and wake_on_ext0 is not None:
            try:
                wake_on_ext0(pin=KEY_GPIO_IN, level=False)
                print(f"✓ ESP32 external wakeup enabled on GPIO{KEY_GPIO_IN}")
            except Exception as e:
                print(f"✗ ESP32 external wakeup setup failed: {e}")

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup all web routes"""

        @self.app.before_request
        async def before_request_handler(request):
            """Update last request time before each request"""
            self.last_web_request_time = time.time()

        @self.app.route("/")
        async def index(request):
            """Main web page"""
            html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Tank Monitor</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    max-width: 800px;
                    margin: 20px auto;
                    padding: 20px;
                    background-color: #f0f0f0;
                }
                .container {
                    background-color: white;
                    border-radius: 10px;
                    padding: 30px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                h1 {
                    color: #333;
                    border-bottom: 2px solid #4CAF50;
                    padding-bottom: 10px;
                }
                .info-box {
                    background-color: #f9f9f9;
                    border-left: 4px solid #4CAF50;
                    padding: 15px;
                    margin: 15px 0;
                }
                .info-box h3 {
                    margin-top: 0;
                    color: #4CAF50;
                }
                button {
                    background-color: #4CAF50;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                    margin: 5px;
                }
                button:hover { background-color: #45a049; }
                button.danger { background-color: #d32f2f; }
                button.danger:hover { background-color: #c62828; }
                button.upload { background-color: #ff9800; }
                button.upload:hover { background-color: #e68900; }
                #upload-progress { display: none; margin-top: 10px; }
                .progress-bar {
                    width: 100%;
                    height: 20px;
                    background-color: #ddd;
                    border-radius: 4px;
                    overflow: hidden;
                }
                .progress-fill {
                    height: 100%;
                    background-color: #ff9800;
                    width: 0%;
                    transition: width 0.3s;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⏱️ Tank Level Monitor V1.7.0</h1>

                <div class="info-box">
                    <h3>⏰ Current Time (Berlin)</h3>
                    <div id="datetime" style="font-size: 16px; font-weight: bold; color: #4CAF50;">Loading...</div>
                </div>

                <div class="info-box">
                    <h3>📊 Current Measurement</h3>
                    <div style="font-family: monospace; font-size: 14px;">
                        <div><span id="measure-time" style="color: #4CAF50; font-weight: bold;">--:--:--</span></div>
                        <div style="padding: 10px 0; border-top: 1px solid #ddd; border-bottom: 1px solid #ddd;">
                            <span id="val1">0</span> | <span id="val2">0</span> | <span id="val3">0</span> | <span id="val4" style="font-weight: bold; color: #4CAF50;">0</span>
                        </div>
                    </div>
                </div>

                <div class="info-box">
                    <h3>🌡️ Temperature Sensors</h3>
                    <div style="font-family: monospace; font-size: 13px;" id="temp-readings">
                        <div style="color: #999;">No sensors detected</div>
                    </div>
                </div>

                <!--
                <div class="info-box">
                    <h3>⚡ Power Supply</h3>
                    <div style="font-family: monospace; font-size: 14px;">
                        <div><b>VBUS:</b> <span id="vbus-voltage" style="color: #4CAF50; font-weight: bold;">--</span> V</div>
                    </div>
                </div>
                -->

                <div class="info-box">
                    <button onclick="publishCurrent()">📤 Publish</button>
                    <button onclick="downloadLog()">📥 Download Log</button>
                    <button class="danger" onclick="exitWebMode()">🔴 Exit Web Mode</button>
                </div>

                <div class="info-box">
                    <h3>📡 System Status</h3>
                    <div id="status">Loading...</div>
                    <hr style="margin: 10px 0; border: none; border-top: 1px solid #ddd;">
                    <div><b>Memory:</b> <span id="memory">--</span></div>
                </div>

                <div class="info-box">
                    <h3>🔧 Firmware Update</h3>
                    <input type="file" id="firmware-file" accept=".mpy">
                    <button class="upload" onclick="uploadFirmware()">📤 Upload Firmware</button>
                    <button class="upload" id="launch-button" onclick="launchFirmware()" style="display: none;">🚀 Launch Firmware</button>
                    <div id="upload-progress">
                        <div class="progress-bar">
                            <div id="upload-progress-fill" class="progress-fill"></div>
                        </div>
                        <div id="upload-status" style="margin-top: 5px;"></div>
                    </div>
                </div>
            </div>

            <script>
                async function updateStatus() {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();
                        document.getElementById('datetime').textContent = data.time;
                        document.getElementById('measure-time').textContent = data.measurement_time;
                        document.getElementById('val1').textContent = data.norm_dist[0];
                        document.getElementById('val2').textContent = data.norm_dist[1];
                        document.getElementById('val3').textContent = data.norm_dist[2];
                        document.getElementById('val4').textContent = data.norm_dist[3];
                        document.getElementById('status').innerHTML =
                            `<b>Mode:</b> WEB<br>` +
                            `<b>WiFi:</b> ${data.wifi_connected ? '✓ Connected' : '✗ Disconnected'}`;
                        document.getElementById('memory').textContent = data.memory;

                        /*
                        // Update VBUS voltage
                        if (data.vbus_voltage !== undefined && data.vbus_voltage >= 0) {
                            const vbusV = (data.vbus_voltage / 1000).toFixed(2);
                            document.getElementById('vbus-voltage').textContent = vbusV;
                        }
                        */

                        // Update temperature readings
                        const tempDiv = document.getElementById('temp-readings');
                        if (data.temperatures && data.temperatures.length > 0) {
                            let tempHtml = '';
                            for (let i = 0; i < data.temperatures.length; i++) {
                                const [serial, temp] = data.temperatures[i];
                                const tempC = (temp / 10).toFixed(1);
                                tempHtml += `<div>${serial}: <b>${tempC}°C</b></div>`;
                            }
                            tempDiv.innerHTML = tempHtml;
                        } else {
                            tempDiv.innerHTML = '<div style="color: #999;">No sensors detected</div>';
                        }
                    } catch (e) {
                        console.error('Status error: ' + e);
                    }
                }

                async function publishCurrent() {
                    try {
                        const response = await fetch('/api/publish');
                        const data = await response.json();
                        await updateStatus();
                    } catch (e) {
                        console.error('Publish error: ' + e);
                    }
                }

                async function downloadLog() {
                    window.location.href = '/api/log';
                }

                async function uploadFirmware() {
                    const file = document.getElementById('firmware-file').files[0];
                    if (!file) {
                        return;
                    }

                    const progressDiv = document.getElementById('upload-progress');
                    const progressFill = document.getElementById('upload-progress-fill');
                    const statusDiv = document.getElementById('upload-status');
                    const launchButton = document.getElementById('launch-button');

                    progressDiv.style.display = 'block';
                    progressFill.style.width = '0%';
                    statusDiv.textContent = 'Uploading...';
                    launchButton.style.display = 'none';

                    try {
                        const response = await fetch('/api/upload', {
                            method: 'POST',
                            body: file
                        });

                        const data = await response.json();
                        if (data.status === 'ok') {
                            progressFill.style.width = '100%';
                            statusDiv.textContent = '✓ Upload successful! ' + data.size + ' bytes';
                            statusDiv.style.color = '#4CAF50';
                            launchButton.style.display = 'inline-block';
                        } else {
                            statusDiv.textContent = '✗ Upload failed: ' + data.message;
                            statusDiv.style.color = '#d32f2f';
                        }
                    } catch (e) {
                        statusDiv.textContent = '✗ Error: ' + e;
                        statusDiv.style.color = '#d32f2f';
                    }
                }

                async function launchFirmware() {
                    try {
                        const response = await fetch('/api/launch', {
                            method: 'POST'
                        });

                        const data = await response.json();
                        if (data.status === 'ok') {
                            setTimeout(() => {
                                window.location.reload();
                            }, 2000);
                        }
                    } catch (e) {
                        // Server restarting is expected
                    }
                }

                async function exitWebMode() {
                    try {
                        const response = await fetch('/api/exit');
                        const data = await response.json();
                    } catch (e) {
                        // Server shutting down is expected
                    }
                }

                updateStatus();
                setInterval(updateStatus, 500);
            </script>
        </body>
        </html>
        """
            return Response(html, headers={"Content-Type": "text/html"})

        @self.app.route("/api/status")
        async def api_status(request):
            """Return current status"""
            try:
                self.update_datetime_string()
                wifi_connected = self.wlan.isconnected()
                
                # Format temperature readings as list of [serial, reading] pairs
                temp_data = []
                for rom_hex, temp_int in self.temperature_readings:
                    temp_data.append([rom_hex, temp_int])

                return Response(json.dumps({
                    "time": self.current_datetime_str,
                    "measurement_time": self.last_measurement_time,
                    "wifi_connected": wifi_connected,
                    "norm_dist": self.distance_measurements,
                    "temperatures": temp_data,
                    #"vbus_voltage": self.vbus_voltage,
                    "memory": get_memory_usage()
                }), headers={"Content-Type": "application/json"})
            except Exception as e:
                return Response(json.dumps({"error": str(e)}), status_code=500)   

        @self.app.route("/api/publish")
        async def api_publish(request):
            """Publish current measurement"""
            try:
                if self.distance_measurements:
                    await self.publish_distance_measurement(self.distance_measurements)
                    await self.publish_temperature_measurements(self.temperature_readings)
                    #await self.publish_vbus_voltage(self.vbus_voltage)
                    await self.log_measurement()
                    return Response(json.dumps({"status": "Published"}))
                return Response(json.dumps({"status": "No measurement"}))
            except Exception as e:
                return Response(json.dumps({"error": str(e)}), status_code=500)

        @self.app.route("/api/log")
        async def api_log(request):
            """Download log file in 1KB chunks"""
            try:
                async def stream_log():
                    try:
                        with open(LOGFILE, "r") as f:
                            while True:
                                chunk = f.read(1024)
                                if not chunk:
                                    break
                                yield chunk
                    except Exception as e:
                        yield f"Error reading file: {str(e)}"

                return Response(stream_log(), headers={"Content-Type": "text/csv", "Content-Disposition": "attachment; filename=log.csv"})
            except Exception as e:
                return Response(f"Error: {str(e)}", status_code=500)

        @self.app.route('/api/upload', methods=['POST'])
        async def api_upload(request):
            """Upload new firmware"""
            try:
                gc.collect()
                content_length = int(request.headers.get('Content-Length', 0))
                bytes_written = 0

                with open('/main_new.mpy', 'wb') as f:
                    if request.body:
                        data = request.body
                        if isinstance(data, str):
                            data = data.encode('utf-8')
                        f.write(data)
                        bytes_written = len(data)

                    if hasattr(request, 'stream') and request.stream and bytes_written < content_length:
                        while bytes_written < content_length:
                            remaining = content_length - bytes_written
                            chunk_size = min(2048, remaining)
                            chunk = await request.stream.read(chunk_size)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytes_written += len(chunk)
                            await asyncio.sleep(0)

                if bytes_written == 0:
                    return Response('{"status": "error", "message": "No file received"}',
                                  status_code=400, headers={'Content-Type': 'application/json'})

                print(f"Upload: {bytes_written} bytes")
                return Response(f'{{"status": "ok", "size": {bytes_written}}}',
                              headers={'Content-Type': 'application/json'})
            except Exception as e:
                print(f"Upload error: {e}")
                return Response('{"status": "error", "message": "Upload failed"}',
                              status_code=500, headers={'Content-Type': 'application/json'})

        @self.app.route('/api/launch', methods=['POST'])
        async def api_launch(request):
            """Launch new firmware and restart"""
            try:
                print("Launch: Replacing main.mpy with main_new.mpy...")
                os.rename('/main_new.mpy', '/main_tank.mpy')
                print("Launch: Firmware replaced, restarting...")

                global launch_restart_pending
                launch_restart_pending = True

                return Response('{"status": "ok"}', headers={'Content-Type': 'application/json'})
            except Exception as e:
                print(f"Launch error: {e}")
                return Response('{"status": "error"}', status_code=500,
                              headers={'Content-Type': 'application/json'})

        @self.app.route("/api/exit")
        async def api_exit(request):
            """Exit web mode and shutdown server"""
            self.web_mode_active = False
            self.web_server_running = False
            print("Web mode exit requested, shutting down server...")
            response = Response(json.dumps({"status": "Exiting"}))
            # Shutdown the server after sending response
            self.app.shutdown()
            return response

    def connect_wifi(self):
        """Connect to WiFi"""
        #machine.Pin(23,machine.Pin.OUT).high()
        time.sleep(.1)
        self.wlan.active(True)
        if PLATFORM=="ESP32" :
            self.wlan.config(dhcp_hostname=HOSTNAME)      
        if not self.wlan.isconnected():
            print(f"Connecting to {WIFI_SSID}...")
            #self.wlan.connect(WIFI_SSID, WIFI_PASSWORD, bssid=WIFI_BSSID) # bssid only works for fritzbox, not repeaters
            self.wlan.connect(WIFI_SSID, WIFI_PASSWORD)

            timeout = 20
            while not self.wlan.isconnected() and timeout > 0:
                print(".", end="")
                time.sleep(1)
                timeout -= 1

            if self.wlan.isconnected():
                print("\n✓ WiFi connected")
                return True
            else:
                print("\n✗ WiFi failed")
                return False
        return True
    
    def disconnect_wifi(self):
        """Disconnect from WiFi"""
        if self.wlan:
            self.wlan.disconnect()
            self.wlan.active(False)
            if PLATFORM_NAME=="RPI_PICO_W":
                self.wlan.deinit()
            self.wlan=None
        else:
            print("ERROR: wifi already disconnected")

    def sync_time(self):
        """Sync time via NTP"""
        try:
            self.update_datetime_string()          
            ntptime.settime()
            self.update_datetime_string()
            print("✓ NTP synced")
            return True
        except Exception as e:
            print(f"✗ NTP failed: {e}")
            return False

    def update_datetime_string(self):
        """Update datetime string"""
        time_struct = time.gmtime(time.time())
        year = time_struct[0]
        month = time_struct[1]
        day = time_struct[2]
        hour = time_struct[3]
        minute = time_struct[4]
        second = time_struct[5]

        self.current_datetime_str = f"{day:02d}.{month:02d}.{year} {hour:02d}:{minute:02d}:{second:02d}"

    def init_mqtt(self):
        """Initialize MQTT"""
        if mqtt is None:
            print("WARNING: MQTT not available")
            return False

        try:
            print(f"Connecting to MQTT {MQTT_SERVER}:{MQTT_PORT}...")
            self.mqtt_client = mqtt.MQTTClient(HOSTNAME, MQTT_SERVER, MQTT_PORT)
            self.mqtt_client.connect()
            print("✓ MQTT connected")

            # Send startup message with timestamp
            self.update_datetime_string()
            #topic = "tank/1/status"
            #message = f"{self.current_datetime_str},hello"
            #self.mqtt_client.publish(topic, message)
            #print(f"✓ Status: {message}")

            return True
        except Exception as e:
            print(f"✗ MQTT failed: {e}")
            return False

    async def perform_measurement(self, publish=True, log=True):
        """Perform a measurement

        Args:
            publish: If True, publish to MQTT
            log: If True, log to CSV
        """
        try:
            activate_sr04_module(True)
            await asyncio.sleep_ms(500)

            readings = []
            for i in range(3):
                vals = []
                for j in range(5):
                    dist = measure_distance_mm()
                    if dist > 0:
                        vals.append(dist)
                    await asyncio.sleep_ms(100)
                if vals:
                    readings.append(median(vals))
                else:
                    readings.append(0)                                
            
            activate_sr04_module(False)
            self.distance_measurements=convert_dist(readings)

            self.temperature_readings = await measure_temperatures()

            # Measure VBUS voltage (async, non-blocking)
            #self.vbus_voltage = await measure_vbus_voltage()

            if publish:
                await self.publish_distance_measurement(self.distance_measurements)
                await self.publish_temperature_measurements(self.temperature_readings)
                #await self.publish_vbus_voltage(self.vbus_voltage)
            if log:
                await self.log_measurement()
            print(f"✓ Measurement: {self.distance_measurements}")
            await asyncio.sleep(1)
            

        except Exception as e:
            print(f"✗ Measurement error: {e}")           
            return None

    async def publish_distance_measurement(self, norm_dist):
        """Publish via MQTT"""
        if self.mqtt_client is None:
            return False

        try:
            self.last_measurement_time = self.current_datetime_str
            topic = "tank/1/level"
            message = f"{self.current_datetime_str},{norm_dist[0]},{norm_dist[1]},{norm_dist[2]},{norm_dist[3]}"
            self.mqtt_client.publish(topic, message)
            print(f"✓ MQTT: {message}")
            return True
        except Exception as e:
            print(f"✗ MQTT publish failed: {e}")
            return False

    async def publish_temperature_measurements(self, temp_readings):
        """Publish individual temperature readings via MQTT

        Args:
            temp_readings: List of tuples (sensor_id, temp_int) for each sensor
        """
        if self.mqtt_client is None:
            return False

        try:
            for sensor_id, temp_int in temp_readings:                
                # DS18B20 sensors use their ROM address
                topic = f"tank/1/temp/{sensor_id}"
                message = f"{self.current_datetime_str},{temp_int}"
                self.mqtt_client.publish(topic, message)
                print(f"✓ MQTT Temp: {message} -> {topic}")
            return True
        except Exception as e:
            print(f"✗ MQTT temp publish failed: {e}")
            return False

    # async def publish_vbus_voltage(self, vbus_mv):
    #     """Publish VBUS voltage via MQTT

    #     Args:
    #         vbus_mv: VBUS voltage in mV (e.g., 5000 for 5.0V)
    #     """
    #     if self.mqtt_client is None or vbus_mv < 0:
    #         return False

    #     try:
    #         topic = "tank/1/vbus"
    #         vbus_v = vbus_mv / 1000.0
    #         message = f"{self.current_datetime_str},{vbus_mv}"
    #         self.mqtt_client.publish(topic, message)
    #         print(f"✓ MQTT VBUS: {vbus_v:.2f}V -> {topic}")
    #         return True
    #     except Exception as e:
    #         print(f"✗ MQTT VBUS publish failed: {e}")
    #         return False

    async def log_measurement(self):
        """Log to CSV"""
        try:            
            csv_line = f"{self.current_datetime_str}"
            for value in self.distance_measurements:                
                csv_line+=f",{value}"                
            for device, value in self.temperature_readings:
                # 1wire ID: letztes byte is CRC                
                csv_line+=f",{device},{value}"
            csv_line+="\n"

            file_exists = False
            try:
                with open(LOGFILE, "r") as f:
                    if os.stat(LOGFILE)[6]>(1024*1024):
                        os.remove(LOGFILE)
                    else:
                        file_exists = True                    
            except:
                pass
            
            # Stop writing file >1MB. Should be enough for one season.           
            with open(LOGFILE, "a") as f:
                if not file_exists:
                    f.write("time,h1,h2,h3,V,d,td,f1,t1,f2,t2,f3,t3,f4,t4,f5,t5\n")                
                f.write(csv_line)
                f.flush()

            return True
        except Exception as e:
            print(f"✗ Log failed: {e}")
            return False

    async def key_monitor_task(self):
        key_is_pressed = False

        while True:
            current_pin = self.key_pin.value()
            current_time = time.ticks_ms()

            if current_pin == 0 and not key_is_pressed:
                self.key_press_time = current_time
                key_is_pressed = True
                print("Key pressed")

            elif current_pin == 1 and key_is_pressed:
                await asyncio.sleep_ms(20)
                if self.key_pin.value() == 1:
                    duration = time.ticks_diff(current_time, self.key_press_time) / 1000.0
                    key_is_pressed = False

                    if duration > 10:
                        print(f"Reset by key")
                        machine.reset()
                        
                    #elif duration >= 5.0:
                    #    self.web_mode_active = False
                    #    # Shutdown server if running
                    #    if self.web_server_running:
                    #        self.app.shutdown()
                    #    self.web_server_running = False
                    #    print("Web mode force disabled")

            await asyncio.sleep_ms(100)
    
    def get_seconds(self):
        current_struct = time.gmtime(time.time())      
        minutes = current_struct[4]
        seconds = current_struct[5]
        seconds_from_last_hour=minutes*60+seconds
        return seconds_from_last_hour

    def get_sleeptime(self):
        if T_aus <= TEMP_5MIN_WAKEUP:
            wakeup_h=TIMEOUT_5MIN_WAKEUP
        elif T_aus <= TEMP_15MIN_WAKEUP:
            wakeup_h=TIMEOUT_15MIN_WAKEUP
        else:
            wakeup_h=TIMEOUT_REPORT_WAKEUP
                 
        wakeup_r=TIMEOUT_REPORT_WAKEUP
        seconds_from_last_hour=self.get_seconds()
        tto_h=seconds_from_last_hour%wakeup_h
        tsleep_h=wakeup_h-tto_h        
        if tsleep_h<wakeup_h/2:
            tto_h=tsleep_h
            tsleep_h+=wakeup_h
        tto_r=seconds_from_last_hour%wakeup_r
        tsleep_r=wakeup_r-tto_r       
        if tsleep_r<wakeup_r/2:
            tto_r=tsleep_r
            tsleep_r+=wakeup_r

        tsleep=min(tsleep_h,tsleep_r)
        is_report=tto_r<=tto_h+1
        return tsleep,is_report                 

    def deep_sleep(self):
        print("deepsleep")
        self.status_led.off()
        activate_temp_module(False)                 
        self.disconnect_wifi()
        tsleep, _=self.get_sleeptime()
        # Calculate sleep time to next full hour
        if PLATFORM_NAME=="RPI_PICO_W":
            # https://github.com/tomjorquera/pico-micropython-lowpower-workaround
            tsleep=60                                
        else:                    
            if DEVICE_SIMSLEEP:
                # Simulate deepsleep behavior
                while tsleep>0 and self.key_pin.value()!=0:
                    tsleep-=0.1
                    time.sleep_ms(100)
                machine.reset()
            else:
                machine.deepsleep(tsleep*1000) # in ms. rpy cannot sleep longer than 30seconds
                # will reset after sleep

    async def measurement_task(self):       
        while True:
            try:
                await self.perform_measurement()
                # After measurement, sleep until next full hour
                if not self.web_mode_active:
                   self.deep_sleep()
                else:
                    # In web mode, wait for a while
                    await asyncio.sleep(60)
            except Exception as e:
                print(f"✗ Measurement task error: {e}")
                await asyncio.sleep(10)

    async def ntp_sync_task(self):
        """Periodic NTP sync"""
        last_sync = 0
        while True:
            try:
                current_time = time.time()
                if current_time - last_sync > 24 * 60 * 60:
                    if self.connect_wifi():
                        if self.sync_time():
                            last_sync = current_time
                await asyncio.sleep(60)
            except Exception as e:
                print(f"NTP task error: {e}")
                await asyncio.sleep(60)

    async def datetime_update_task(self):
        """Continuously update datetime string (every second)"""
        while True:
            try:
                self.update_datetime_string()
                await asyncio.sleep(1)
            except Exception as e:
                print(f"DateTime update error: {e}")
                await asyncio.sleep(1)

    async def restart_monitor_task(self):
        """Monitor and handle device restart flag"""
        while True:
            try:
                global launch_restart_pending
                if launch_restart_pending:
                    print("Restart: Device is restarting...")
                    await asyncio.sleep(0.5)
                    machine.reset()
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"Restart monitor error: {e}")
                await asyncio.sleep(0.1)

    async def web_mode_measurement_task(self):
        """Take measurements every 10 seconds while in web mode (no publish)"""
        while True:
            if self.web_mode_active and self.web_server_running:
                try:
                    # Measure and log, but don't publish (only on button press)
                    await self.perform_measurement(publish=False, log=False)
                    # Update measurement time for web display
                    self.last_measurement_time = self.current_datetime_str
                except Exception as e:
                    print(f"Web mode measurement error: {e}")
            await asyncio.sleep(10)

    async def watchdog_task(self):
        """Feed the watchdog timer periodically and monitor web inactivity"""
        while True:
            try:
                self.wdt.feed()
                print("✓ Watchdog fed")

                # Check web interface inactivity
                if self.web_mode_active and self.web_server_running and self.last_web_request_time > 0:
                    current_time = time.time()
                    inactive_time = current_time - self.last_web_request_time
                    if inactive_time > WEBSERVER_REQUEST_TIMEOUT:
                        print(f"Web interface inactive for {inactive_time:.0f}s, resetting...")
                        machine.reset()

                await asyncio.sleep(5)
            except Exception as e:
                print(f"Watchdog error: {e}")
                await asyncio.sleep(5)

    async def led_task(self):
        """Control status LED - 1s on at startup, then blink in web mode"""
        # Light for 1 second at startup
       
        while True:
            try:
                if self.web_mode_active and self.web_server_running:
                    # In web mode with server running: blink 500ms on, 500ms off
                    self.status_led.on()
                    await asyncio.sleep_ms(100)
                    self.status_led.off()
                    await asyncio.sleep_ms(900)
                else:
                    await asyncio.sleep_ms(100)

            except Exception as e:
                print(f"LED task error: {e}")
                await asyncio.sleep_ms(100)

    async def web_server_task(self):
        """Web server - starts when web_mode_active is True, stops when False"""
        server = None
        while True:
            # Wait for web mode to be activated
            while not self.web_mode_active:
                await asyncio.sleep(0.1)

            print("Starting Microdot web server...")
            self.web_server_running = True

            if self.wlan.isconnected():
                ip = self.wlan.ifconfig()[0]
                print(f"✓ Access at: http://{ip}")
                print(f"✓ Hostname: {HOSTNAME}")

            # Run server while web_mode_active is True
            try:
                # start_server() blocks, but we handle shutdown via try/finally
                await self.app.start_server(port=80, debug=False)
            except OSError as e:
                # Port might be in use or socket closed
                print(f"Web server error: {e}")
            except Exception as e:
                print(f"Web server exception: {e}")
            finally:
                # Always execute this when server stops (for any reason)
                self.web_server_running = False

            # Check if we should stay in sleep mode or exit web mode
            if not self.web_mode_active:
                print("✓ Web server stopped, returning to sleep")
                self.deep_sleep()

    async def run(self):
        global T_aus
        """Main async run loop"""
        self.status_led.on()
        print(f"Tank Level Monitor [{PLATFORM}]")        
        activate_temp_module(True)
        await asyncio.sleep_ms(10)
        # Measure temperatures, the first reading is bad
        await measure_temperatures()
        temperature_readings = await measure_temperatures()

        # Activate web mode if KEY is pressed at startup or after wake
        if self.key_pressed_at_startup:
            self.web_mode_active = True
            print("✓ Web mode auto-activated (KEY pressed at startup)")
        else:
            # Only send data if temperatures are in critical range or it is time to report.
            # Otherwise save battery.
            # See ALARM_TEMP_THRESHOLD_* constants above
            aus_temp=[value for name,value in temperature_readings if name == '1-AUS']
            crit_temp=[value for name,value in temperature_readings if name not in ['1-AUS', 'device']]          
            is_alarm=True # alarm also if no sensors available
            if aus_temp and crit_temp:
                aus_temp=min(aus_temp)
                min_temp=min(crit_temp)
                T_aus=aus_temp                
                is_alarm=(aus_temp<ALARM_TEMP_THRESHOLD_AUS and min_temp<ALARM_TEMP_THRESHOLD_HIGH) or min_temp<ALARM_TEMP_THRESHOLD_LOW
            tsleep,is_report=self.get_sleeptime()
            print(f"is_alarm:{is_alarm}, is_report:{is_report}, tsleep:{tsleep}")                           
            if not (is_alarm or is_report):
                self.deep_sleep()        

        # Initialize
        print("Connecting to WiFi...")
        if self.connect_wifi():
            self.sync_time()
            self.init_mqtt()

        # Run all tasks
        print("Starting tasks...")
        await asyncio.gather(
            self.key_monitor_task(),
            self.measurement_task(),
            #self.ntp_sync_task(),
            self.datetime_update_task(),
            self.restart_monitor_task(),
            self.web_mode_measurement_task(),
            self.watchdog_task(),
            self.led_task(),
            self.web_server_task()
        )


def run(key_pressed_at_startup):
    try:
        monitor = TankMonitor()
        monitor.key_pressed_at_startup=key_pressed_at_startup
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        print("\nShutdown")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        monitor.deep_sleep()



######################################
# Startup code
######################################

def start():

    print("=" * 60)
    print("Boot sequence starting...")
    print("=" * 60)
    gc.collect()

    #
    # >5s, abort boot:
    # Hold KEY and then CTRL-C to enter REPL.
    # When deep_sleep is executed the device will restart and we are caught in endless startup loop otherwise!
    #

    if KEY_GPIO_IN is not None:
        print(f"\n[{PLATFORM_NAME}] Press KEY for 5 seconds to abort boot...")
        print("Release before 5s to proceed with boot")
        
        key_pin = Pin(KEY_GPIO_IN, Pin.IN, Pin.PULL_UP)
        pressed_time = 0
        if key_pin.value() == 0:      # Button pressed (pulled to GND):
            pressed_start=time.ticks_ms()
            while key_pin.value() == 0:
                time.sleep_ms(100)
            pressed_time=(time.ticks_ms()-pressed_start)

        # Load main application if keypress less 3s, otherwise quit boot
        if pressed_time<5000:
            try:        
                # Clean up memory before loading main                
                print("\nLoading main application...")         
                run(pressed_time>100)            
            except Exception as e:
                print(f"❌ ERROR: Failed to load main")
                sys.print_exception(e)    


