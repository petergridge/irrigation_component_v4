from .irrigationzone import irrigationzone
import logging
import asyncio
import voluptuous as vol
from datetime import timedelta
import math
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import async_generate_entity_id
from homeassistant.helpers.event import async_track_state_change

from homeassistant.helpers.restore_state import (
    RestoreEntity,
)

from homeassistant.components.switch import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SwitchEntity,
)

from .const import (
    DOMAIN,
    ATTR_START,
    ATTR_HIDE_CONFIG,
    ATTR_RUN_FREQ,
    ATTR_RUN_DAYS,
    ATTR_IRRIGATION_ON,
    ATTR_RAIN_SENSOR,
    ATTR_IGNORE_RAIN_BOOL,
    CONST_SWITCH,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_DISABLE_ZONE,
    ATTR_ZONES,
    ATTR_ZONE,
    ATTR_PUMP,
    ATTR_FLOW_SENSOR,
    ATTR_WATER,
    ATTR_WATER_ADJUST,
    ATTR_WAIT,
    ATTR_REPEAT,
    ATTR_REMAINING,
    DFLT_ICON_WAIT,
    DFLT_ICON_RAIN,
    DFLT_ICON,
    ATTR_LAST_RAN,
    ATTR_MONITOR_CONTROLLER,
    ATTR_MULTIPLE,
    ATTR_RESET,
)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    ATTR_ENTITY_ID,
    CONF_SWITCHES,
    CONF_UNIQUE_ID,
    CONF_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ATTR_ICON,
    MATCH_ALL,
)

SWITCH_SCHEMA = vol.All(
    vol.Schema(
        {
        vol.Required(ATTR_START): cv.entity_domain('input_datetime'),
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
        vol.Optional(ATTR_IRRIGATION_ON): cv.entity_domain('input_boolean'),
        vol.Optional(ATTR_HIDE_CONFIG): cv.entity_domain('input_boolean'),
        vol.Optional(ATTR_MONITOR_CONTROLLER): cv.entity_domain('binary_sensor'),
        vol.Optional(ATTR_ICON,default=DFLT_ICON): cv.icon,
        vol.Optional(ATTR_MULTIPLE,default=False): cv.boolean,
        vol.Optional(ATTR_RESET,default=False): cv.boolean,
        vol.Required(ATTR_ZONES): [{
            vol.Required(ATTR_ZONE, 'zone'): cv.entity_domain(CONST_SWITCH),
            vol.Optional(ATTR_PUMP, 'pump'): cv.entity_domain(CONST_SWITCH),
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(ATTR_FLOW_SENSOR): cv.entity_domain(['input_number','sensor']),
            vol.Required(ATTR_WATER): cv.entity_domain('input_number'),
            vol.Optional(ATTR_WATER_ADJUST): cv.entity_domain(['input_number','sensor']),
            vol.Optional(ATTR_WAIT): cv.entity_domain('input_number'),
            vol.Optional(ATTR_REPEAT): cv.entity_domain('input_number'),
            vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
            vol.Optional(ATTR_RAIN_SENSOR): cv.entity_domain('binary_sensor'),
            vol.Optional(ATTR_IGNORE_RAIN_SENSOR): vol.All(vol.Any(cv.entity_domain('input_boolean'),cv.boolean)),
            vol.Optional(ATTR_DISABLE_ZONE): vol.All(vol.Any(cv.entity_domain('input_boolean'),cv.boolean)),
            vol.Optional(ATTR_ICON,default=DFLT_ICON): cv.icon,
        }],
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        }
    ),
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_SWITCHES): cv.schema_with_slug_keys(SWITCH_SCHEMA)}
)

_LOGGER = logging.getLogger(__name__)


async def _async_create_entities(hass, config):
    '''Create the Template switches.'''
    switches = []

    for device, device_config in config[CONF_SWITCHES].items():
        friendly_name           = device_config.get(CONF_NAME, device)
        start_time              = device_config.get(ATTR_START)
        hide_config             = device_config.get(ATTR_HIDE_CONFIG)
        run_freq                = device_config.get(ATTR_RUN_FREQ)
        irrigation_on           = device_config.get(ATTR_IRRIGATION_ON)
        multiple                = device_config.get(ATTR_MULTIPLE)
        reset                   = device_config.get(ATTR_RESET)
        icon                    = device_config.get(ATTR_ICON)
        zones                   = device_config.get(ATTR_ZONES)
        unique_id               = device_config.get(CONF_UNIQUE_ID)
        monitor_controller      = device_config.get(ATTR_MONITOR_CONTROLLER)

        switches.append(
            IrrigationProgram(
                hass,
                device,
                friendly_name,
                start_time,
                hide_config,
                run_freq,
                irrigation_on,
                monitor_controller,
                multiple,
                reset,
                icon,
                DFLT_ICON_WAIT,
                DFLT_ICON_RAIN,
                zones,
                unique_id,
            )
        )

    return switches


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    '''Set up the irrigation switches.'''
    async_add_entities(await _async_create_entities(hass, config))

    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        'set_run_zone',
        {
            vol.Required(ATTR_ZONE): cv.string,
        },
        "entity_run_zone",
    )


class IrrigationProgram(SwitchEntity, RestoreEntity):
    '''Representation of an Irrigation program.'''
    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        start_time,
        hide_config,
        run_freq,
        irrigation_on,
        monitor_controller,
        multiple,
        reset,
        icon,
        wait_icon,
        rain_icon,
        zones,
        unique_id,
    ):

        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, device_id, hass=hass
        )

        '''Initialize a Irrigation program.'''
        self._name               = str(friendly_name).title()
        self._program_name       = str(friendly_name).title()
        self._start_time         = start_time
        self._hide_config        = hide_config
        self._run_freq           = run_freq
        self._irrigation_on      = irrigation_on
        self._monitor_controller = monitor_controller
        self._icon               = icon
        self._wait_icon          = wait_icon
        self._rain_icon          = rain_icon
        self._zones              = zones
        self._state_attributes   = None
        self._state              = False
        self._unique_id          = unique_id
        self._stop               = False
        self._device_id          = device_id
        self._last_run           = None
        self._triggered_manually = True
        self._template           = None
        self._allow_multiple_zones = multiple
        self._reset_last_ran     = reset
        self._irrigationzones    = []
        self._run_zone           = None
        ''' Validate and Build a template from the attributes provided '''

        _LOGGER.debug('Start Time %s: %s',self._start_time, hass.states.get(self._start_time))
        template = "states('sensor.time')" + " + ':00' == states('" + self._start_time + "') "

        if self._irrigation_on is not None:
            _LOGGER.debug('Irrigation on %s: %s',self._irrigation_on, hass.states.get(self._irrigation_on))
            template = template + " and is_state('" + self._irrigation_on + "', 'on') "
        if self._monitor_controller is not None:
            _LOGGER.debug('Controller on %s: %s',self._irrigation_on, hass.states.get(self._irrigation_on))
            template = template + " and is_state('" + self._monitor_controller + "', 'on') "

        template = "{{ " + template + " }}"

        _LOGGER.debug('-------------------- on start: %s ----------------------------',self._name)
        _LOGGER.debug('Template: %s', template)

        template       = cv.template(template)
        template.hass  = hass
        self._template = template


    @callback
    def _update_state(self, result):
        super()._update_state(result)

    async def async_added_to_hass(self):

        state = await self.async_get_last_state()
        try:
            self._last_run = state.attributes.get(ATTR_LAST_RAN)
            ''' handle breaking change from change of date format'''
            try:
                z = dt_util.as_timestamp(self._last_run)
            except:
                self._last_run = dt_util.now() - timedelta(days=10)
        except:
            ''' default to 10 days ago for new programs '''
            if self._last_run is None:
                self._last_run = dt_util.now() - timedelta(days=10)

        self._ATTRS = {}
        self._ATTRS [ATTR_LAST_RAN]    = self._last_run
        self._ATTRS [ATTR_REMAINING]   = ('%d:%02d:%02d' % (0, 0, 0))
        self._ATTRS [ATTR_START]       = self._start_time
        self._ATTRS [ATTR_HIDE_CONFIG] = self._hide_config

        if self._run_freq is not None:
            self._ATTRS [ATTR_RUN_FREQ] = self._run_freq
        if self._irrigation_on is not None:
            self._ATTRS [ATTR_IRRIGATION_ON] = self._irrigation_on
        if self._monitor_controller is not None:
            self._ATTRS [ATTR_MONITOR_CONTROLLER] = self._monitor_controller

        ''' zone loop to set the attributes '''
        self._total_runtime = 0
        zn = 0

        for zone in self._zones:
            zn += 1

            self._irrigationzones.append (irrigationzone(self.hass, zone,self._run_freq))

            ''' check if the zone name has changed or is new and reset last run time '''
            a = ('zone%s_%s' % (zn, CONF_NAME))
            try:
                z_name = state.attributes.get(a)
            except:
                z_name = None
            a = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            try:
                z_last_ran = state.attributes.get(a)
            except:
                z_last_run = None
            if z_name != zone.get(CONF_NAME):
                z_last_ran = None
            self._ATTRS [a] = z_last_ran
            self._irrigationzones[zn-1].set_last_ran(z_last_ran)
            zoneremaining = ('zone%s_remaining' % (zn))
            self._ATTRS [zoneremaining] = ('%d:%02d:%02d' % (0, 0, 0))

            ''' Build Zone Attributes to support the custom card '''
            a = ('zone%s_%s' % (zn, CONF_NAME))
            self._ATTRS [a] = zone.get(CONF_NAME)
            a = ('zone%s_%s' % (zn, ATTR_WATER))
            self._ATTRS [a] = zone.get(ATTR_WATER)
            if zone.get(ATTR_FLOW_SENSOR) is not None:
                a = ('zone%s_%s' % (zn, ATTR_FLOW_SENSOR))
                self._ATTRS [a] = zone.get(ATTR_FLOW_SENSOR)
            if zone.get(ATTR_WAIT) is not None:
                a = ('zone%s_%s' % (zn, ATTR_WAIT))
                self._ATTRS [a] = zone.get(ATTR_WAIT)
            if zone.get(ATTR_REPEAT) is not None:
                a = ('zone%s_%s' % (zn, ATTR_REPEAT))
                self._ATTRS [a] = zone.get(ATTR_REPEAT)
            if zone.get(ATTR_WATER_ADJUST) is not None:
                a = ('zone%s_%s' % (zn, ATTR_WATER_ADJUST))
                self._ATTRS [a] = zone.get(ATTR_WATER_ADJUST)
            if zone.get(ATTR_RUN_FREQ) is not None:
                a = ('zone%s_%s' % (zn, ATTR_RUN_FREQ))
                self._ATTRS [a] = zone.get(ATTR_RUN_FREQ)
            if zone.get(ATTR_RAIN_SENSOR) is not None:
                a = ('zone%s_%s' % (zn, ATTR_RAIN_SENSOR))
                self._ATTRS [a] = zone.get(ATTR_RAIN_SENSOR)
            if zone.get(ATTR_IGNORE_RAIN_SENSOR) is not None:
                a = ('zone%s_%s' % (zn, ATTR_IGNORE_RAIN_SENSOR))
                self._ATTRS [a] = zone.get(ATTR_IGNORE_RAIN_SENSOR)
            if zone.get(ATTR_DISABLE_ZONE) is not None:
                a = ('zone%s_%s' % (zn, ATTR_DISABLE_ZONE))
                self._ATTRS [a] = zone.get(ATTR_DISABLE_ZONE)

        self._ATTRS ['zone_count'] = zn
        setattr(self, '_state_attributes', self._ATTRS)

        ''' house keeping to help ensure solenoids are in a safe state '''
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, self.async_turn_off())

        @callback
        async def template_check(entity, old_state, new_state):
            self.async_schedule_update_ha_state(True)

        @callback
        def template_sensor_startup(event):
            '''Triggered when HASS has fully started'''

            ''' Validate the referenced objects now that HASS has started'''
            if  self.hass.states.async_available('sensor.time'):
                _LOGGER.error('%s not defined check your configuration, ' + \
                                'if sensor.time has not been defined the irriagtion program will not behave as expected' \
                                ,'sensor.time')

            if  self.hass.states.async_available(self._start_time):
                _LOGGER.error('%s not found, check your configuration, ' + \
                                'if the entity has not been defined the irriagtion program will not run as expected' \
                                ,self._start_time)

            if self._irrigation_on is not None:
                if  self.hass.states.async_available(self._irrigation_on):
                    _LOGGER.warning('%s not found, check your configuration',self._irrigation_on)

            if self._monitor_controller is not None:
                if  self.hass.states.async_available(self._monitor_controller):
                    _LOGGER.warning('%s not found, check your configuration',self._monitor_controller)

            if self._run_freq is not None:
                if  self.hass.states.async_available(self._run_freq):
                    _LOGGER.warning('%s not found, check your configuration',self._run_freq)

            ''' run validation over the zones '''
            zn = 0
            for zone in self._zones:
                x = self._irrigationzones[zn-1].validate()
                zn += 1

            '''Update template on startup '''
            async_track_state_change(
                self.hass, 'sensor.time', template_check)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

        await super().async_added_to_hass()

    def entity_run_zone(self, zone: str) -> None:
        self._run_zone = zone
        self._triggered_manually = True

    @property
    def name(self):
        '''Return the name of the variable.'''
        return self._name

    @property
    def unique_id(self):
        '''Return the unique id of this switch.'''
        return self._unique_id

    @property
    def is_on(self):
        '''Return true if light is on.'''
        return self._state

    @property
    def should_poll(self):
        '''If entity should be polled.'''
        return False

    @property
    def icon(self):
        '''Return the icon to be used for this entity.'''
        return self._icon

    @property
    def state_attributes(self):
        '''Return the state attributes.
        Implemented by component base class.
        '''
        return self._state_attributes

    async def async_update(self):

        '''Update the state from the template.'''
        if self._state == False:
            if self._template.async_render():
                self._run_zone = None
                self._triggered_manually = False
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):

        def format_run_time(runtime):
            hourmin = divmod(runtime,3600)
            minsec = divmod(hourmin[1],60)
            return ('%d:%02d:%02d' % (hourmin[0], minsec[0], minsec[1]))

        ''' Initialise for stop programs service call '''
        z_zone_found  = False
        p_icon        = self._icon
        p_name        = self._name
        self._stop    = False
        self._state   = True
        self.async_schedule_update_ha_state()
        step = 1

        ''' use this to set the last ran attribute of the zones '''
        p_last_ran = dt_util.now()

        ''' if the zone has run update the last run attribute for the zone  '''
        state = await self.async_get_last_state()

        ''' zone loop to calculate the total run time '''
        self._total_runtime = 0
        track_total = True
        zn = 0
        for zone in self._zones:
            z_run_freq    = zone.get(ATTR_RUN_FREQ,self._run_freq)
            z_name        = zone.get(CONF_NAME)
            zn += 1
            a = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            z_last_ran = state.attributes.get(a)

            if zone.get(ATTR_FLOW_SENSOR) is not None:
                track_total = False

            ''' check if the zone should run '''
            ''' Request made to run only a zone '''
            if self._run_zone:
                if z_name != self._run_zone:
                    continue

            if self._irrigationzones[zn-1].disable_zone_value() == True:
                zoneremaining = ('zone%s_remaining' % (zn))
                self._ATTRS [zoneremaining] = ('%d:%02d:%02d' % (0, 0, 0))
                continue
            if not self._triggered_manually:
                if self._irrigationzones[zn-1].is_raining():
                    continue
                if z_run_freq is not None:
                    if self._irrigationzones[zn-1].should_run() == False:
                        continue

            x = self._irrigationzones[zn-1].run_time()
            self._total_runtime += self._irrigationzones[zn-1].run_time()
            zoneremaining = ('zone%s_remaining' % (zn))

            if zone.get(ATTR_FLOW_SENSOR) is not None:
                self._ATTRS [zoneremaining] = self._irrigationzones[zn-1].run_time()
            else:
                self._ATTRS [zoneremaining] = format_run_time(self._irrigationzones[zn-1].run_time())

            '''Set time remaining attribute '''
            if track_total == False:
                self._ATTRS [ATTR_REMAINING] = 'N/A'
            else:
                self._ATTRS [ATTR_REMAINING] = format_run_time(self._total_runtime)
            setattr(self, '_state_attributes', self._ATTRS)
            self.async_schedule_update_ha_state()
        ''' end of for zone loop to calculate total run time '''

        ''' Iterate through all the defined zones and run when required'''
        zn = 0
        for zone in self._zones:
            z_run_freq    = zone.get(ATTR_RUN_FREQ,self._run_freq)
            z_name        = zone.get(CONF_NAME)

            zn += 1
            a = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            z_last_ran = state.attributes.get(a)

            ''' check if the zone should run '''
            if self._run_zone:
                if z_name != self._run_zone:
                    await asyncio.sleep(1)
                    continue

            if self._irrigationzones[zn-1].disable_zone_value() == True:
                zoneremaining = ('zone%s_remaining' % (zn))
                if zone.get(ATTR_FLOW_SENSOR) is not None:
                    self._ATTRS [zoneremaining] = '0'
                else:
                    self._ATTRS [zoneremaining] = ('%d:%02d:%02d' % (0, 0, 0))
                continue

            if self._irrigationzones[zn-1].run_time() <= 0:
                continue

            if not self._triggered_manually:
                if self._irrigationzones[zn-1].is_raining():
                    continue
                if z_run_freq is not None:
                    if self._irrigationzones[zn-1].should_run() == False:
                        continue

            if self._stop == True:
                break

            loop = asyncio.get_event_loop()
            loop.create_task(self._irrigationzones[zn-1].async_turn_on())

            ''' a short wait to let the zone catch up '''
            await asyncio.sleep(1)

            while self._irrigationzones[zn-1].state() != 'off':
                current_state = self._irrigationzones[zn-1].state()
                self._name = self._program_name + "-" + self._irrigationzones[zn-1].name()
                if self._irrigationzones[zn-1].state() == 'on':
                    self._icon = self._irrigationzones[zn-1].icon()

                if self._irrigationzones[zn-1].state() == 'eco':
                    self._icon = self._wait_icon
                if self._ATTRS [ATTR_REMAINING] != 'N/A':
                    self._total_runtime -= step
                    if self._total_runtime <= 0:
                        self._total_runtime = 0
                    '''Set time remaining attributes '''
                    self._ATTRS [ATTR_REMAINING] = format_run_time(self._total_runtime)

                zoneremaining = ('zone%s_remaining' % (zn))
                if zone.get(ATTR_FLOW_SENSOR) is not None:
                    self._ATTRS [zoneremaining] = self._irrigationzones[zn-1].remaining_time()
                else:
                    self._ATTRS [zoneremaining] = format_run_time(self._irrigationzones[zn-1].remaining_time())

                setattr(self, '_state_attributes', self._ATTRS)

                self.async_schedule_update_ha_state()
                self.async_write_ha_state()
                await asyncio.sleep(1)

            ''' Update the zones last ran time '''
            zonelastran = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            if not self._triggered_manually and not self._stop:
                self._ATTRS[zonelastran] = p_last_ran
                self._irrigationzones[zn-1].set_last_ran(p_last_ran)
            ''' reset the last ran time to 23 hours ago '''
            if self._reset_last_ran:
                self._ATTRS[zonelastran] = dt_util.now() - timedelta(hours=23)
            ''' reset the time remaining to 0 '''
            zoneremaining = ('zone%s_remaining' % (zn))
            if zone.get(ATTR_FLOW_SENSOR) is not None:
                self._ATTRS [zoneremaining] = ('0')
            else:
                self._ATTRS [zoneremaining] = ('%d:%02d:%02d' % (0, 0, 0))

            setattr(self, '_state_attributes', self._ATTRS)
            result = self.async_schedule_update_ha_state()
        ''' end of for zone loop '''

        if not self._triggered_manually and not self._stop:
            self._ATTRS [ATTR_LAST_RAN] = p_last_ran

        if zone.get(ATTR_FLOW_SENSOR) is not None:
            self._ATTRS [ATTR_REMAINING] = '0'
        else:
            self._ATTRS [ATTR_REMAINING] = ('%d:%02d:%02d' % (0, 0, 0))

        setattr(self, '_state_attributes', self._ATTRS)

        self._run_zone              = None
        self._state                 = False
        self._stop                  = False
        self._triggered_manually    = True
        self._icon                  = p_icon
        self._name                  = self._program_name

        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):

        self._stop          = True
        self._run_zone      = None

        zn = 0
        for zone in self._zones:

            await self._irrigationzones[zn].async_turn_off()
            zn += 1
            zoneremaining = ('zone%s_remaining' % (zn))
            self._ATTRS [zoneremaining] = ('%d:%02d:%02d' % (0, 0, 0))
            setattr(self, '_state_attributes', self._ATTRS)

        self._state = False
        self.async_schedule_update_ha_state()