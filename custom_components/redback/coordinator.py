"""DataUpdateCoordinator for the Redback integration."""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import DOMAIN, LOGGER, SCAN_INTERVAL, TEST_MODE
from .redbacklib import RedbackInverter, TestRedbackInverter, RedbackError, RedbackAPIError, RedbackConnectionError


class RedbackDataUpdateCoordinator(DataUpdateCoordinator):
    """The Redback Data Update Coordinator."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the Redback coordinator."""
        self.config_entry = entry
        clientSession1 = async_get_clientsession(hass)
        clientSession2 = async_get_clientsession(hass)

        # RedbackInverter is the API connection to the Redback cloud portal
        if TEST_MODE:
            self.redback = TestRedbackInverter(
                client_id=entry.data["client_id"], client_secret=entry.data["client_secret"], session1=clientSession1, site_index=entry.data["site_index"], session2=clientSession2, portalEmail=entry.data["portal_email"], portalPassword=entry.data["portal_password"]
            )
        else:
            self.redback = RedbackInverter(
                client_id=entry.data["client_id"], client_secret=entry.data["client_secret"], session1=clientSession1, site_index=entry.data["site_index"], session2=clientSession2, portalEmail=entry.data["portal_email"], portalPassword=entry.data["portal_password"]
            )

        super().__init__(hass, LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self):
        """Fetch system status from Redback."""
        LOGGER.debug(
            "Syncing data with Redback (entry_id=%s)", self.config_entry.entry_id
        )

        try:
            # the Redback integration has built-in timers to rate-limit the data updates and not hammer the API
            self.inverter_info = await self.redback.getInverterInfo()
            self.energy_data = await self.redback.getEnergyData()
        except RedbackError as err:
            raise UpdateFailed(f"HTTP error: {err}") from err
        except RedbackConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except RedbackAPIError as err:
            LOGGER.debug(f"API error: {err}")
            raise ConfigEntryAuthFailed("Invalid credentials") from err

        return self.energy_data

