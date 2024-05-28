"""Redback sensors for the Redback integration."""
from __future__ import annotations
from collections.abc import Mapping

from datetime import (datetime, timedelta)
from typing import Any
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.config_entries import ConfigEntry

import re

from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfFrequency,
    UnitOfTemperature,
    PERCENTAGE,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.number import (
    NumberEntity,
    NumberDeviceClass,
    NumberEntityDescription,
)
    
from .const import DOMAIN, LOGGER, INVERTER_MODES, INVERTER_STATUS, PHASES, FAN_STATE
from .entity import RedbackEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entities"""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    hasBattery = await coordinator.redback.hasBattery()
    batteryCount = await coordinator.redback.getBatteryCount()
    phaseCount = await coordinator.redback.getPhaseCount()
    pvCount = await coordinator.redback.getPvCount()
    cabinetCount = await coordinator.redback.getBatteryCabinetCount()
    

    # Private API has different entities
    # Note: private API always creates battery entities, need examples without
    # battery so the hasBattery() method can be updated to suit
    
    entities = [
        RedbackDateTimeSensor(
            coordinator,
            {
                "name": "Inverter Set End Time",
                "id_suffix": "inverter_set_end_time",
                "data_source": "InverterSetEndTime",
            },
        ),
        RedbackVoltageSensor(
            coordinator,
            {
                "name": "Grid Combined Voltage",
                "id_suffix": "grid_v",
                "data_source": "VoltageInstantaneousV",
            },
        ),

        RedbackCurrentSensor(
            coordinator,
            {
                "name": "Grid Combined Current",
                "id_suffix": "grid_a_net",
                "data_source": "CurrentInstantaneousA",
            },
        ),
        RedbackTempSensor(
            coordinator,
            {
                "name": "Inverter Temperature",
                "id_suffix": "inverter_temp",
                "data_source": "InverterTemperatureC",
            },
        ),
        RedbackFrequencySensor(
            coordinator,
            {
                "name": "Grid Combined Frequency",
                "id_suffix": "grid_freq",
                "data_source": "FrequencyInstantaneousHz",
            },
        ),
        RedbackEnergyMeter(
            coordinator,
            {
                "name": "Site All Time PV Generation Energy",
                "id_suffix": "site_alltime_pv_total",
                "data_source": "PvAllTimeEnergykWh",
            },
        ),
        RedbackEnergyMeter(
            coordinator,
            {
                "name": "Site All Time Load Energy",
                "id_suffix": "site_alltime_load_total",
                "data_source": "LoadAllTimeEnergykWh",
            },
        ),
        RedbackEnergyMeter(
            coordinator,
            {
                "name": "Site All Time Export Energy",
                "id_suffix": "site_alltime_export_total",
                "data_source": "ExportAllTimeEnergykWh",
            },
        ),
        RedbackEnergyMeter(
            coordinator,
            {
                "name": "Site All Time Import Energy",
                "id_suffix": "site_alltime_import_total",
                "data_source": "ImportAllTimeEnergykWh",
            },
        ),

        RedbackPowerSensor(
            coordinator,
            {
                "name": "Grid Combined Power Export",
                "id_suffix": "grid_export",
                "data_source": "ActiveExportedPowerInstantaneouskW",
            },
        ),
        RedbackPowerSensor(
            coordinator,
            {
                "name": "Grid Combined Power Import",
                "id_suffix": "grid_import",
                "data_source": "ActiveImportedPowerInstantaneouskW",
            },
        ),
        RedbackPowerSensor(
            coordinator,
            {
                "name": "Grid Combined Power Net",
                "id_suffix": "grid_net",
                "data_source": "ActiveNetPowerInstantaneouskW",
            },
        ),
        RedbackPowerSensor(
            coordinator,
            {
                "name": "PV Combined Generation Power",
                "id_suffix": "pv_power",
                "data_source": "PvPowerInstantaneouskW",
            },
        ),
        RedbackPowerSensor(
            coordinator,
            {
                "name": "Site Power Load",
                "id_suffix": "load_power",
                "data_source": "$calc$ float(ed['PvPowerInstantaneouskW']) + float(ed['BatteryPowerNegativeIsChargingkW'] if ed['BatteryPowerNegativeIsChargingkW'] else 0) - float(ed['ActiveExportedPowerInstantaneouskW']) + float(ed['ActiveImportedPowerInstantaneouskW'])",
            },
        ),
        RedbackStatusSensor(
            coordinator,
            {
                "name": "Inverter Status",
                "id_suffix": "inverter_status",
                "data_source": "Status",
            }
        ),
        RedbackPowerSensorW(
            coordinator,
            {
                "name": "Inverter Power Setpoint",
                "id_suffix": "inverter_powerW",
                "data_source": "InverterPowerW",
            },
        ),
        RedbackInverterModeSensor(
            coordinator,
            {
                "name": "Inverter Mode",
                "id_suffix": "inverter_mode",
                "data_source": "InverterMode",
            },
        ),
    ]
    count = 0
    while count < phaseCount:
        entities.extend([
            RedbackVoltageSensor(
                coordinator,
                {
                    "name": f"Grid Phase {PHASES[count]} Voltage",
                    "id_suffix": f"grid_phase_{PHASES[count]}_v",
                    "data_source": f"VoltageInstantaneousV_{PHASES[count]}",
                },
            ),
            RedbackCurrentSensor(
                coordinator,
                {
                    "name": f"Grid Phase {PHASES[count]} Current",
                    "id_suffix": f"grid_phase_{PHASES[count]}_current",
                    "data_source": f"CurrentInstantaneousA_{PHASES[count]}",
                },
            ),
            RedbackPowerSensor(
            coordinator,
            {
                "name": f"Grid Phase {PHASES[count]} Power Net",
                "id_suffix": f"grid_{PHASES[count]}_power_net",
                "data_source": f"ActiveNetPowerInstantaneouskW_{PHASES[count]}",
            },
            ),
            RedbackPowerSensor(
            coordinator,
            {
                "name": f"Grid Phase {PHASES[count]} Power Import",
                "id_suffix": f"grid_{PHASES[count]}_power_import",
                "data_source": f"ActiveImportedPowerInstantaneouskW_{PHASES[count]}",
            },
            ),
            RedbackPowerSensor(
            coordinator,
            {
                "name": f"Grid Phase {PHASES[count]} Power Export",
                "id_suffix": f"grid_{PHASES[count]}_power_export",
                "data_source": f"ActiveExportedPowerInstantaneouskW_{PHASES[count]}",
            },
            ),
        ])
        count += 1
    count = 0
    while count < pvCount:
        count += 1
        entities.extend([
            RedbackVoltageSensor(
                coordinator,
                {
                    "name": f"PV MPPT {count} Voltage",
                    "id_suffix": f"pv_mppt_{count}_v",
                    "data_source": f"PV_{str(count)}_VoltageV",
                },
            ),
            RedbackCurrentSensor(
                coordinator,
                {
                    "name": f"PV MPPT {count} Current",
                    "id_suffix": f"pv_mppt_{count}_a",
                    "data_source": f"PV_{str(count)}_CurrentA",
                },
            ),
            RedbackPowerSensor(
                coordinator,
                {
                    "name": f"PV MPPT {count} Power",
                    "id_suffix": f"pv_mppt_{count}_power",
                    "data_source": f"PV_{str(count)}_PowerkW",
                },
            ),
        ])
        
    count = 0
    while count < batteryCount:
        count += 1
        module = count 
        entities.extend([
            RedbackPowerSensor(
                coordinator,
                {
                    "name": f"Battery Module {module} Power Flow",
                    "id_suffix": f"battery_module_{module}_power",
                    "data_source": f"Battery_{module}_PowerNegativeIsChargingkW",
                },
            ),
            RedbackChargeSensor(
                coordinator,
                {
                    "name": f"Battery Module {module} SoC",
                    "id_suffix": f"battery_module_{module}_soc",
                    "data_source": f"Battery_{module}_SoC0To1",
                    "convertPercent": True,
                },
            ),
            RedbackVoltageSensor(
                coordinator,
                {
                    "name": f"Battery Module {module} Voltage",
                    "id_suffix": f"battery_module_{module}_v",
                    "data_source": f"Battery_{module}_VoltageV",
                },
            ),
            RedbackCurrentSensor(
                coordinator,
                {
                    "name": f"Battery Module {module} Current",
                    "id_suffix": f"battery_module_{module}_a",
                    "data_source": f"Battery_{module}_CurrentNegativeIsChargingA",
                },
            ),
        ])
    count=0
    while count < cabinetCount:
        count += 1
        entities.extend([
            RedbackTempSensor(
                coordinator,
                {
                    "name": f"Battery Cabinet {count} Temperature",
                    "id_suffix": f"battery_cabinet_{count}_temp",
                    "data_source": f"Battery_Cabinet_{str(count)}_TemperatureC",
                },
            ),
            RedBackFanStateSensor(
                coordinator,
                {
                    "name": f"Battery Cabinet {count} Fan",
                    "id_suffix": f"battery_cabinet_{count}_fan",
                    "data_source": f"Battery_Cabinet_{str(count)}_FanState",
                },
            ),
        ])
        
    if hasBattery:
        entities.extend([
            RedbackEnergyMeter(
                coordinator,
                {
                    "name": "Battery All Time Charge Energy",
                    "id_suffix": "site_alltime_battery_charge_total",
                    "data_source": "BatteryChargeAllTimeEnergykWh",
                },
            ),
            RedbackEnergyMeter(
                coordinator,
                {
                    "name": "Battery All Time Discharge Energy",
                    "id_suffix": "site_alltime_battery_discharge_total",
                    "data_source": "BatteryDischargeAllTimeEnergykWh",
                },
            ),
            RedbackVoltageSensor(
                coordinator,
                {
                    "name": "Battery Stack Voltage",
                    "id_suffix": "battery_stack_v",
                    "data_source": "Battery_Total_VoltageV",
                },
            ),
            RedbackChargeSensor(
                coordinator,
                {
                    "name": "Battery Stack SoC",
                    "id_suffix": "battery_stack_soc",
                    "data_source": "BatterySoCInstantaneous0to1",
                    "convertPercent": True,
                },
            ),
            RedbackPowerSensor(
                coordinator,
                {
                    "name": "Battery Stack Power Flow",
                    "id_suffix": "battery_stack_power",
                    "data_source": "BatteryPowerNegativeIsChargingkW",
                },
            ),
            RedbackPowerSensor(
                coordinator,
                {
                    "name": "Battery Stack Power Discharge",
                    "id_suffix": "battery_stack_discharge",
                    "data_source": "BatteryPowerNegativeIsChargingkW",
                    "direction": "positive",
                },
            ),
            RedbackPowerSensor(
                coordinator,
                {
                    "name": "Battery Stack Power Charge",
                    "id_suffix": "battery_stack_charge",
                    "data_source": "BatteryPowerNegativeIsChargingkW",
                    "direction": "negative",
                },
            ),
            RedbackEnergyStorageSensor(
                coordinator,
                {
                    "name": "Battery Stack Capacity",
                    "id_suffix": "battery_stack_capacity",
                    "data_source": "BatteryCapacitykWh",
                },
            ),
            RedbackBatteryChargeSensor(
                coordinator,
                {
                    "name": "Battery Stack Current Energy",
                    "id_suffix": "battery_stack_current_storage",
                    "data_source": "",
                },
            ),
        ])

    async_add_entities(entities)

class RedbackChargeSensor(RedbackEntity, SensorEntity):
    """Sensor for battery state-of-charge"""

    _attr_name = None
    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    
    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information."""
        dataAttributes = self.coordinator.inverter_info

        if dataAttributes is None:
            data["min_offgrid_soc_0to1"] = None
            data["min_ongrid_soc_0to1"] = None
        else:
            data = {
                "min_offgrid_soc_0to1": (dataAttributes["MinOffgridSoC0to1"] ),
                "min_ongrid_soc_0to1": (dataAttributes["MinSoC0to1"] )
            }
        return data
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        if self.convertPercent: self._attr_native_value *= 100
        self.async_write_ha_state()
 
class RedbackTempSensor(RedbackEntity, SensorEntity):
    """Sensor for temperature"""

    _attr_name = "Temperature"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()

class RedbackFrequencySensor(RedbackEntity, SensorEntity):
    """Sensor for frequency"""

    _attr_name = "Frequency"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfFrequency.HERTZ
    _attr_device_class = SensorDeviceClass.FREQUENCY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()

class RedbackVoltageSensor(RedbackEntity, SensorEntity):
    """Sensor for voltage"""

    _attr_name = "Voltage"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data.get(self.data_source, 0)
        self.async_write_ha_state()

class RedbackPowerSensor(RedbackEntity, SensorEntity):
    """Sensor for power"""

    _attr_name = "Power"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
    _attr_device_class = SensorDeviceClass.POWER

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)

        measurement = 0
        # dynamically calculated power measurement
        if self.data_source.startswith("$calc$"):
            measurement = re.sub(r"^\$calc\$\s*", "", self.data_source)
            ed = self.coordinator.energy_data
            measurement = float(eval(measurement, {"ed":ed}))

        # direct power measurement
        else:
            measurement = self.coordinator.energy_data[self.data_source]

        if (self.direction == "positive"):
            measurement = max(measurement, 0)
        elif (self.direction == "negative"):
            measurement = 0 - min(measurement, 0)
        self._attr_native_value = measurement
        if self.convertkW: self._attr_native_value /= 1000 # convert from W to kW
        self.async_write_ha_state()
        
class RedbackPowerSensorW(RedbackEntity, SensorEntity):
    _attr_name = "Power"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data.get(self.data_source, 0)
        self.async_write_ha_state()

class RedbackDateTimeSensor(RedbackEntity, SensorEntity):
    """Sensor for datetime"""

    _attr_name = "DateTime"
    #_attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    #_attr_native_unit_of_measurement = UnitOfTime.
    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()
    

    
class RedbackEnergyMeter(RedbackEntity, SensorEntity):
    """Sensor for energy metering"""

    _attr_name = "Energy Meter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()

class RedbackEnergyStorageSensor(RedbackEntity, SensorEntity):
    """Sensor for energy storage"""

    _attr_name = "Energy Storage"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE 
    _attr_icon = "mdi:home-battery"

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information."""
        dataAttributes = self.coordinator.inverter_info

        if dataAttributes is None:
            data["usable_battery_offgrid_kwh"] = None
            data["usable_battery_ongrid_kwh"] = None
            data["max_discharge_power_w"] = None
            data["max_charge_power_w"] = None
        else: 
            data = {
				"usable_battery_offgrid_kwh": dataAttributes["UsableBatteryCapacitykWh"],
				"usable_battery_ongrid_kwh": dataAttributes["UsableBatteryCapacityOnGridkWh"],
				"max_discharge_power_w": dataAttributes["BatteryMaxDischargePowerW"],
				"max_charge_power_w": dataAttributes["BatteryMaxChargePowerW"]
			}
        return data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        # note: this sensor type always draws from inverter_info, not energy_data
        self._attr_native_value = self.coordinator.inverter_info[self.data_source]
        self.async_write_ha_state()

class RedbackCurrentSensor(RedbackEntity, SensorEntity):
    """Sensor for Current"""

    _attr_name = "Current"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _suggested_display_precision = 3

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = round(self.coordinator.energy_data[self.data_source],0)
        self.async_write_ha_state()

class RedBackInverterSet(RedbackEntity, NumberEntity):
    """Sensor for inverter set power"""

    _attr_name = "Inverter Set Power"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_value = 0
    _attr_mode = "box"
    

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value

class RedBackFanStateSensor(RedbackEntity, SensorEntity):
    """Sensor for Fan State"""

    _attr_name = "State"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = FAN_STATE
    _attr_native_unit_of_measurement = None
    _attr_icon = "mdi:fan"

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()

class RedbackStatusSensor(RedbackEntity, SensorEntity):
    """Sensor for state"""

    _attr_name = "State"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = INVERTER_STATUS
    _attr_native_unit_of_measurement = None
    _attr_icon = "mdi:information-outline"

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information."""
        dataAttributes = self.coordinator.inverter_info

        if dataAttributes is None:
            data["serial_number"] = None
            data["software_version"] = None
            data["ross_version"] = None
            data["model_name"] = None
            data["system_type"] = None
            data["site_id"] = None
            data ["inverter_max_export_power_w"] = None
            data ["inverter_max_import_power_w"] = None
            
        else: 
            data = {
				"serial_number": dataAttributes["SerialNumber"],
				"software_version": dataAttributes["SoftwareVersion"],
				"ross_version": dataAttributes["SoftwareVersion"],
                "model_name": dataAttributes["ModelName"],
                "system_type": dataAttributes["SystemType"],
                "site_id": dataAttributes["SiteId"],
                "inverter_max_export_power_w": dataAttributes["InverterMaxExportPowerW"],
                "inverter_max_import_power_w": dataAttributes["InverterMaxImportPowerW"]
			}
        return data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.inverter_info[self.data_source]
        self.async_write_ha_state()
        
class RedbackInverterModeSensor(RedbackEntity, SensorEntity):
    """Sensor for inverter mode"""

    _attr_name = "state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = INVERTER_MODES
    _attr_native_unit_of_measurement = None
    _attr_icon = "mdi:information-outline"

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information."""
        dataAttributes = self.coordinator.energy_data

        if dataAttributes is None:
            data["inverter_power_setting"] = None
        else: 
            data = {
				"inverter_power_setting": dataAttributes["InverterPowerW"]
			}
        return data


    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        self._attr_native_value = self.coordinator.energy_data[self.data_source]
        self.async_write_ha_state()
        
class RedbackBatteryChargeSensor(RedbackEntity, SensorEntity):
    """Sensor for inverter mode"""

    _attr_name = "Energy Storage"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE 
    _attr_icon = "mdi:home-battery"

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return additional pieces of information."""
        dataAttributesEnergy = self.coordinator.energy_data
        dataAttributesInfo = self.coordinator.inverter_info

        data = {
		    "battery_current_ongrid_usable": round( ((dataAttributesEnergy["BatterySoCInstantaneous0to1"]  - dataAttributesInfo["MinSoC0to1"]) * dataAttributesInfo["BatteryCapacitykWh"]), 3),
            "battery_current_offgrid_usable": round( ((dataAttributesEnergy["BatterySoCInstantaneous0to1"] - dataAttributesInfo["MinOffgridSoC0to1"]) * dataAttributesInfo["BatteryCapacitykWh"]), 3),
			}
        return data

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        LOGGER.debug("Updating entity: %s", self.unique_id)
        batterySoc= self.coordinator.energy_data["BatterySoCInstantaneous0to1"]
        batteryCapacity= self.coordinator.inverter_info["BatteryCapacitykWh"]
        self._attr_native_value = round( (batterySoc * batteryCapacity), 3)
        self.async_write_ha_state()
        

        
