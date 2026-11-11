"""Config flow for Gobel Battery Monitor integration."""
import glob
import logging
import os
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_BMS_TYPE,
    CONF_CONNECTION_TYPE,
    CONF_BATTERY_PORT,
    CONF_IP_ADDRESS,
    CONF_IP_PORT,
    CONF_USB_PORT,
    CONF_BAUD_RATE,
    CONF_POLL_INTERVAL,
    CONF_JK_DISPLAY_INDEX_START,
    CONF_MAX_PARALLEL,
    BMS_TYPES,
    CONNECTION_TYPES,
    BATTERY_PORTS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_PARALLEL,
    DEFAULT_BAUD_RATE,
    DEFAULT_IP_PORT,
    DEFAULT_JK_DISPLAY_INDEX_START,
)

_LOGGER = logging.getLogger(__name__)


def _list_serial_ports():
    """Return candidate serial paths (by-id first, then by-path, then raw ttys)."""
    ports = []
    for pattern in (
        "/dev/serial/by-id/*",
        "/dev/serial/by-path/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    ):
        ports.extend(sorted(glob.glob(pattern)))
    return ports


class GobelBatteryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gobel Battery."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        errors = {}
        if user_input is not None:
            self.config_data = user_input
            if user_input[CONF_CONNECTION_TYPE] in ["ethernet", "wifi"]:
                return await self.async_step_network()
            else:
                return await self.async_step_serial()

        data_schema = vol.Schema(
            {
                vol.Required("device_name", default="Gobel Battery"): str,
                vol.Required(CONF_BMS_TYPE, default=BMS_TYPES[0]): vol.In(BMS_TYPES),
                vol.Required(CONF_CONNECTION_TYPE, default=CONNECTION_TYPES[0]): vol.In(CONNECTION_TYPES),
                vol.Required(CONF_BATTERY_PORT, default=BATTERY_PORTS[0]): vol.In(BATTERY_PORTS),
                vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(CONF_MAX_PARALLEL, default=DEFAULT_MAX_PARALLEL): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(CONF_JK_DISPLAY_INDEX_START, default=DEFAULT_JK_DISPLAY_INDEX_START): vol.In(["00", "01"]),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_network(self, user_input=None):
        """Handle network configuration parameters (IP and port)."""
        errors = {}
        if user_input is not None:
            user_data = {**self.config_data, **user_input}
            unique_id = f"{user_data[CONF_IP_ADDRESS]}_{user_data[CONF_IP_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=user_data["device_name"], data=user_data)

        network_schema = vol.Schema(
            {
                vol.Required(CONF_IP_ADDRESS): str,
                vol.Required(CONF_IP_PORT, default=DEFAULT_IP_PORT): int,
            }
        )

        return self.async_show_form(
            step_id="network", data_schema=network_schema, errors=errors
        )

    async def async_step_serial(self, user_input=None):
        """Handle serial configuration parameters (Port and Baud rate)."""
        errors = {}
        if user_input is not None:
            user_data = {**self.config_data, **user_input}
            unique_id = user_data[CONF_USB_PORT]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=user_data["device_name"], data=user_data)

        serial_schema = vol.Schema(
            {
                vol.Required(CONF_USB_PORT, default="/dev/ttyUSB0"): str,
                vol.Required(CONF_BAUD_RATE, default=DEFAULT_BAUD_RATE): int,
            }
        )

        return self.async_show_form(
            step_id="serial", data_schema=serial_schema, errors=errors
        )

    # ------------------------------------------------------------------
    # Reconfigure: change port / baud / IP of an EXISTING entry in place.
    # Entity & device unique_ids are based on entry_id, so renamed
    # entities and automations are untouched.
    # ------------------------------------------------------------------
    async def async_step_reconfigure(self, user_input=None):
        """Edit the connection settings of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors = {}
        is_net = entry.data.get(CONF_CONNECTION_TYPE) in ("ethernet", "wifi")

        if user_input is not None:
            if not is_net:
                port = user_input[CONF_USB_PORT].strip()
                exists = await self.hass.async_add_executor_job(os.path.exists, port)
                if not exists:
                    errors[CONF_USB_PORT] = "port_not_found"
            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=user_input,
                    reason="reconfigure_successful",
                )

        if is_net:
            schema = vol.Schema(
                {
                    vol.Required(CONF_IP_ADDRESS, default=entry.data.get(CONF_IP_ADDRESS, "")): str,
                    vol.Required(CONF_IP_PORT, default=entry.data.get(CONF_IP_PORT, DEFAULT_IP_PORT)): int,
                    vol.Required(CONF_POLL_INTERVAL, default=entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            )
        else:
            ports = await self.hass.async_add_executor_job(_list_serial_ports)
            current = entry.data.get(CONF_USB_PORT, "")
            if current and current not in ports:
                ports.insert(0, current)
            schema = vol.Schema(
                {
                    vol.Required(CONF_USB_PORT, default=current): SelectSelector(
                        SelectSelectorConfig(
                            options=ports,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(CONF_BAUD_RATE, default=entry.data.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)): int,
                    vol.Required(CONF_POLL_INTERVAL, default=entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): vol.All(vol.Coerce(int), vol.Range(min=1)),
                }
            )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
