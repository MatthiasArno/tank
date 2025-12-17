# =================================================================
# START of Stub overwriting for testing. Uncomment for production.
# =================================================================
device_ids=(bytes.fromhex("28d35452000000d6"), bytes.fromhex("2842d7530000005a"), bytes.fromhex("285b77520000002b"), bytes.fromhex("2863055200000089"), bytes.fromhex("0000000000000049"))
class DS18X20():
    def __init__(self,dummy):                
        self.roms=device_ids
        # -10,0,10,20,30 Celsius
        self.temps=(-10.0, 0.0, 10.0, 20.0, 30.0)
        self.rom2values=dict(zip(self.roms, self.temps))           
    def convert_temp(self):
        pass
    def read_temp(self,rom):
        return self.rom2values[rom]

class OneWire():
    def __init__(self,dummy):
        pass
    def scan(self):
        return device_ids



# TIMEOUT
TIMEOUT_15MIN_WAKEUP=2*60
TIMEOUT_5MIN_WAKEUP=1*60
# NETWORK
MQTT_SERVER="your-server"
WIFI_SSID="your-ssid"


# =================================================================
# END of Stub overwriting for testing. Uncomment for production.
# =================================================================
