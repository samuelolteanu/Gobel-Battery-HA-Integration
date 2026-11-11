"""The Gobel Battery Monitor integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN
from .coordinator import GobelBatteryUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gobel Battery Monitor component from YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Gobel Battery Monitor from a config entry."""
    coordinator = GobelBatteryUpdateCoordinator(hass, entry)
    
    # Run the synchronous driver initialization
    if not await coordinator.async_setup():
        raise ConfigEntryNotReady(f"Failed to connect to BMS for {entry.title}")

    # Fetch initial data so entities have state on startup
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to the sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        # Release socket/serial/background threads
        await hass.async_add_executor_job(coordinator.shutdown)

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Allow deleting stale pack devices (e.g. ghost packs left by a port swap).

    A pack device may be removed only if the BMS is not currently reporting it.
    The "Total" device is never removable.
    """
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    data = (coordinator.data if coordinator else None) or {}
    active = {
        str(item.get("pack_id", i))
        for key in ("analog", "warning")
        for i, item in enumerate(data.get(key, []) or [])
    }
    prefix = f"{entry.entry_id}_pack_"
    for domain, ident in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if ident == f"{entry.entry_id}_total":
            return False
        if ident.startswith(prefix) and ident[len(prefix):] in active:
            return False
    return True
