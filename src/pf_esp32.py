"""
ESP32 D1 NodeMCU - Platform specific configuration
GPIO pin definitions for HC-SR04 and KEY button
"""

# AZ Board: https://www.az-delivery.de/en/blogs/azdelivery-blog-fur-arduino-und-raspberry-pi/das-dreiundzwanzigste-turchen?srsltid=AfmBOoq3zANfTVwCHYACTTIp61QkXzp0ml7nrwgrVSA-XKt5bh0sfA7b
# Allowed Pins: https://randomnerdtutorials.com/esp32-pinout-reference-gpios/

# HC-SR04 Ultrasonic Sensor GPIO
# Pins chosen to be adjacent where possible
SR04_TRIGGER_PIN = 25
SR04_ECHO_PIN = 27
SR04_PWR_OUT = 32

# Button GPIO
KEY_GPIO_IN = 15

# DS18B20 Temperature Sensor (1-Wire)
DS18B20_BUS = 16
DS18B20_PWR = 17

# Platform identifier
PLATFORM_NAME = "ESP32_D1_NODEMCU"

DEVICE_SIMSLEEP = 0
