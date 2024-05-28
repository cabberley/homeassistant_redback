"""Redback sensors for the Redback integration."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.button import (
    ButtonEntity,
)
from homeassistant.helpers import config_validation as cv, entity_platform, service

from .const import DOMAIN,  LOGGER
from .entity import RedbackEntity
import voluptuous as vol
from .coordinator import RedbackDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entities"""

    coordinator: RedbackDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        RedBackInverterModeButton(
            coordinator,
            {
                "name": "Inverter Set Send Change",
                "id_suffix": "inverter_set_send_change",
            },
        ),
    ]
    async_add_entities(entities)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "update_inverter_mode",
        {
            vol.Required('sleep_time'): cv.time_period,
        },
        "set_sleep_timer",
    )

class RedBackInverterModeButton(RedbackEntity, ButtonEntity):
    _attr_icon = "mdi:transmission-tower"

    config_entry: ConfigEntry
    
    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    async def async_press(self, entry=ConfigEntry) -> None:
        self.config_entry = entry
        LOGGER.debug("Inverter Button Pressed A")
        serialNumber = self._attr_device_info["sw_version"]
        serialNumber = self._attr_device_info["serial_number"] 
        inverterMode = await self.coordinator.redback.getInverterSetInfo("mode")
        inverterPower = int(await self.coordinator.redback.getInverterSetInfo("power"))
        inverterDuration = int(await self.coordinator.redback.getInverterSetInfo("duration"))
        newTime = datetime.now(timezone.utc) + timedelta(minutes=int(inverterDuration))
        LOGGER.debug( inverterDuration)
        LOGGER.debug( newTime)
        LOGGER.debug(inverterPower)
        LOGGER.debug(inverterMode)
        swVersion = "2.17.32303.7"
        await self.coordinator.redback.setInverterMode(serialNumber, inverterMode, inverterPower, swVersion)
        await self.coordinator.redback.setInverterSetInfo("end_time", newTime)
        await self.coordinator.redback.setInverterSetInfo("reset", False)
        
