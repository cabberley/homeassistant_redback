"""Redback sensors for the Redback integration."""
from __future__ import annotations
from typing import Any
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.const import (
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.components.number import (
    NumberEntity,
    NumberDeviceClass,
)

from .const import DOMAIN 
from .entity import RedbackEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entities"""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        RedBackInverterSet(
            coordinator,
            {
                "name": "Inverter Set Power",
                "id_suffix": "inverter_set_power",
            },
        ),
        RedBackInverterTimeSet(
            coordinator,
            {
                "name": "Inverter Set Time",
                "id_suffix": "inverter_set_timer",
            },
        )
    ]
    async_add_entities(entities)


class RedBackInverterSet(RedbackEntity, NumberEntity):
    """Sensor for inverter set power"""

    _attr_name = "Inverter Set Power"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_value = 0
    _attr_mode = "box"
    _suggested_display_precision = 0
    _attr_suggested_display_precision = 0
    
    config_entry: ConfigEntry
    
    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        await self.coordinator.redback.setInverterSetInfo("power", value)

class RedBackInverterTimeSet(RedbackEntity, NumberEntity):
    """Sensor for inverter set power"""

    _attr_name = "Inverter Set Timer"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_value = 0
    _attr_mode = "box"
    _suggested_display_precision = 0
    _attr_suggested_display_precision = 0

    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"
    
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = value
        await self.coordinator.redback.setInverterSetInfo("duration", value)
