"""Redback sensors for the Redback integration."""
from __future__ import annotations
from typing import Any
from homeassistant.core import (
    HomeAssistant,
    callback,
)
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.select import (
    SelectEntity,
)

from .const import DOMAIN, INVERTER_MODES_OPTIONS
from .entity import RedbackEntity

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Setup entities"""

    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    entities = [
        RedBackInverterModeSelect(
            coordinator,
            {
                "name": "Inverter Set Mode",
                "id_suffix": "inverter_set_Mode",
            },
        ),
    ]
    async_add_entities(entities)

class RedBackInverterModeSelect(RedbackEntity, SelectEntity):
    _attr_name = "Inverter Set Mode"
    _attr_options = INVERTER_MODES_OPTIONS
    _attr_native_value = 0
    _attr_initial = "Auto"
    _attr_icon = "mdi:transmission-tower"
    _attr_should_poll = False
    _attr_current_option = "Auto"


    @property
    def unique_id(self) -> str:
        """Device Uniqueid."""
        return f"{self.base_unique_id}_{self.id_suffix}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        await self.coordinator.redback.setInverterSetInfo("mode", option)
