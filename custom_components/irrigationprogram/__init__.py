import logging

from .const import (
    DOMAIN,
    CONST_SWITCH,
    SWITCH_ID_FORMAT,
    )


from homeassistant.const import (
#    CONF_SWITCHES,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
#    CONF_TIMEOUT
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


    async def async_run_zone(call):

        zone = call.data.get('zone','')
        entity_id = call.data.get('entity_id','')

        _LOGGER.warning('run zone %s',zone)

        device = SWITCH_ID_FORMAT.format(x)
#        DATA = {ATTR_ENTITY_ID: entity_id}
#        await hass.services.async_call(CONST_SWITCH,
#                                 SERVICE_TURN_ON,
#                                 DATA)

    """ END async_run_zone """



    """ register services """
    hass.services.async_register(DOMAIN,
                                 'stop_programs',
                                 async_stop_programs)

    hass.services.async_register(DOMAIN,
                                 'run_zone',
                                 async_run_zone)

    return True
