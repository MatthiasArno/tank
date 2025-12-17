"""
Raspberry Pi Pico - Platform specific configuration
GPIO pin definitions for HC-SR04 and KEY button
"""

# HC-SR04 Ultrasonic Sensor GPIO
# Pins chosen to be adjacent where possible
SR04_TRIGGER_PIN = 15    # GPIO8 - Trigger output
SR04_ECHO_PIN = 14       # GPIO9 - Echo input
SR04_PWR_OUT = 10      # GPIO10 - Module power control (VCC/GND switching)

# Button GPIO
KEY_GPIO_IN = 16        # Button input with internal pullup
                        # Pulls to GND via 100 Ohm resistor

# DS18B20 Temperature Sensor (1-Wire)
DS18B20_BUS = 10       
DS18B20_PWR = 11

# Platform identifier
PLATFORM_NAME = "RPI_PICO_W"

DEVICE_SIMSLEEP = 1
