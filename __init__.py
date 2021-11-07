import logging

from .const import (
    DOMAIN,
    CONST_SWITCH,
    SWITCH_ID_FORMAT,
    )


from homeassistant.const import (
    CONF_SWITCHES,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_TIMEOUT
    )

# Shortcut for the logger
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):

    platforms = config.get(CONST_SWITCH)

    for x in platforms:
        if x.get('platform') == DOMAIN:
            switches = x.get('switches')
            break

    async def async_stop_programs(call):

        for x in switches:
            if x == call.data.get('ignore',''):
                continue

            device = SWITCH_ID_FORMAT.format(x)
            DATA = {ATTR_ENTITY_ID: device}
            await hass.services.async_call(CONST_SWITCH,
                                     SERVICE_TURN_OFF,
                                     DATA)
    """ END async_stop_switches """

    """ register services """
    hass.services.async_register(DOMAIN,
                                 'stop_programs',
                                 async_stop_programs)

    return True
