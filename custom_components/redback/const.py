"""Constants for the redback integration."""

from homeassistant.const import Platform
from datetime import timedelta
import logging

DOMAIN = "redback"
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT, Platform.BUTTON] 
TEST_MODE = False

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(minutes=1)
SCAN_INTERVAL2 = timedelta(minutes=10)
SCAN_INTERVAL3 = timedelta(minutes=60)

API_METHODS = [
    "public",
    "private",
]

INVERTER_MODES = ["NoMode", "Auto", "ChargeBattery", "DischargeBattery", "ImportPower", "ExportPower", "Conserve", "Offgrid", "Hibernate", "BuyPower", "SellPower", "ForceChargeBattery", "ForceDischargeBattery", "Stop"]
INVERTER_MODES_OPTIONS = ["Auto", "ChargeBattery", "DischargeBattery", "ImportPower", "ExportPower", "Conserve"]
INVERTER_STATUS = ["OK", "Offline", "Fault"]
PHASES = ["A", "B", "C"]
FAN_STATE = ["Off", "On", "Error"]


