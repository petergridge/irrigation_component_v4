
import logging
import asyncio
import voluptuous as vol
from datetime import timedelta
import math
import homeassistant.util.dt as dt_util
from homeassistant.util import slugify
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
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
    ATTR_RUN_FREQ,
    ATTR_RUN_DAYS,
    ATTR_IRRIGATION_ON,
    ATTR_RAIN_SENSOR,
    ATTR_IGNORE_RAIN_BOOL,
    CONST_SWITCH,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_ZONES,
    ATTR_ZONE,
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
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(ATTR_START): cv.entity_domain('input_datetime'),
        vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
        vol.Optional(ATTR_IRRIGATION_ON): cv.entity_domain('input_boolean'),
        vol.Optional(ATTR_MONITOR_CONTROLLER): cv.entity_domain('binary_sensor'),
        vol.Optional(ATTR_ICON,default=DFLT_ICON): cv.icon,
        vol.Optional(ATTR_MULTIPLE,default=False): cv.boolean,
        vol.Required(ATTR_ZONES): [{
            vol.Exclusive(ATTR_ZONE, 'zone'): cv.entity_domain(CONST_SWITCH),
            vol.Required(CONF_NAME): cv.string,
            vol.Optional(ATTR_RUN_FREQ): cv.entity_domain('input_select'),
            vol.Optional(ATTR_RAIN_SENSOR): cv.entity_domain('binary_sensor'),
            vol.Optional(ATTR_IGNORE_RAIN_SENSOR): vol.All(vol.Any(cv.entity_domain('input_boolean'),cv.boolean)),
            vol.Required(ATTR_WATER): cv.entity_domain('input_number'),
            vol.Optional(ATTR_WATER_ADJUST): cv.entity_domain(['input_number','sensor']),
            vol.Optional(ATTR_WAIT): cv.entity_domain('input_number'),
            vol.Optional(ATTR_REPEAT): cv.entity_domain('input_number'),
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
        run_freq                = device_config.get(ATTR_RUN_FREQ)
        irrigation_on           = device_config.get(ATTR_IRRIGATION_ON)
        multiple                = device_config.get(ATTR_MULTIPLE)
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
                run_freq,
                irrigation_on,
                monitor_controller,
                multiple,
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


class IrrigationProgram(SwitchEntity, RestoreEntity):
    '''Representation of an Irrigation program.'''
    def __init__(
        self,
        hass,
        device_id,
        friendly_name,
        start_time,
        run_freq,
        irrigation_on,
        monitor_controller,
        multiple,
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
        self._running            = False
        self._last_run           = None
        self._triggered_manually = True
        self._template           = None
        self._allow_multiple_zones = multiple
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
        self._ATTRS [ATTR_LAST_RAN] = self._last_run
        self._ATTRS [ATTR_REMAINING] = 0
        self._ATTRS [ATTR_START] = self._start_time

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

            a = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            z_last_ran = state.attributes.get(a)
            if state.attributes.get(a) == None:
                ''' default to 10 days ago for new programs '''
                z_last_ran = dt_util.now() - timedelta(days=10)
            self._ATTRS [a] = z_last_ran

            ''' Build Zone Attributes to support the custom card '''
            a = ('zone%s_%s' % (zn, CONF_NAME))
            self._ATTRS [a] = zone.get(CONF_NAME)
            a = ('zone%s_%s' % (zn, ATTR_WATER))
            self._ATTRS [a] = zone.get(ATTR_WATER)
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

            '''Update template on startup '''
            async_track_state_change(
                self.hass, 'sensor.time', template_check)

        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_START, template_sensor_startup)

        await super().async_added_to_hass()


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
        if self._running == False:
            if self._template.async_render():
                self._triggered_manually = False
                loop = asyncio.get_event_loop()
                loop.create_task(self.async_turn_on())

        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):

        def format_run_time(runtime):
            minsec = divmod(runtime,3600)
            hour = minsec[0]
            minsec = divmod(runtime,60)
            return ('%d:%02d:%02d' % (hour, minsec[0], minsec[1]))

        def calculate_run_time(p_water_adj,p_water, p_wait, p_repeat):
            class run_time:
              def __init__(self, run_time, water_adj, water, wait, repeat):
                self.run_time = run_time
                self.water_adj = water_adj
                self.water = water
                self.wait = wait
                self.repeat = repeat

            ''' factor to adjust watering time and calculate run time'''
            z_water_adj = 1
            try:
                if p_water_adj is not None:
                    z_water_adj = float(self.hass.states.get(p_water_adj).state)
                    _LOGGER.debug('watering adjustment factor is %s', z_water_adj)
            except:
                _LOGGER.error('watering adjustment factor is not numeric %s', p_water_adj)

            z_water = math.ceil(int(float(self.hass.states.get(p_water).state)) * float(z_water_adj))
            if z_water == 0:
                _LOGGER.debug('watering time has been adjusted to 0 will not run zone %s',p_water)

            z_wait = 0
            try:
                if p_wait is not None:
                    z_wait = int(float(self.hass.states.get(p_wait).state))
                    _LOGGER.debug('watering adjustment factor is %s', z_water_adj)
            except:
                _LOGGER.error('wait is not numeric %s', p_wait)
                
            z_repeat = 1
            try:
                if p_repeat is not None :
                    z_repeat = int(float(self.hass.states.get(p_repeat).state))
                    if z_repeat == 0:
                        z_repeat = 1
            except:
                _LOGGER.error('repeat is not numeric %s', p_repeat)

            z_run_time = (((z_water + z_wait) * z_repeat) - z_wait) * 60

            return run_time(z_run_time, z_water_adj, z_water, z_wait, z_repeat)
        ''' end calculate_run_time '''

        def should_run(p_run_freq):
            a = ('zone%s_%s' % (zn, ATTR_LAST_RAN))
            z_last_ran = state.attributes.get(a)
            Numeric_Freq = None
            String_Freq = None
            response = True
            if p_run_freq is not None:
                try:
                    Numeric_Freq = int(self.hass.states.get(p_run_freq).state)
                except:
                    String_Freq = self.hass.states.get(p_run_freq).state
                ''' check if this day matches frequency '''
                if Numeric_Freq is not None:
                    if Numeric_Freq <= (dt_util.as_timestamp(dt_util.now()) - dt_util.as_timestamp(z_last_ran)) / 86400:
                        response = True
                    else:
                        response =  False
                if String_Freq is not None:
                    if dt_util.now().strftime('%a') not in String_Freq:
                        response =  False #try next zone#
                    else:
                        response =  True
            return response
        ''' end should_run '''

        def is_raining(p_rain_sensor, p_ignore_rain_sensor):
            ''' assess the rain sensor '''
            raining = True
            ignore_bool = False

            if p_rain_sensor is not None:
                if  self.hass.states.get(p_rain_sensor) == None:
                    _LOGGER.warning('rain sensor: %s not found, check your configuration',p_rain_sensor)
                else:
                    raining = self.hass.states.is_state(p_rain_sensor,'on')
            else:
                raining = False
            ''' assess the ignore rain sensor '''
            if  p_ignore_rain_sensor is not None:
                if  self.hass.states.get(p_ignore_rain_sensor) == None:
                    _LOGGER.warning('Ignore rain sensor: %s not found, check your configuration',p_ignore_rain_sensor)
                else:
                     ignore_bool = self.hass.states.is_state(p_ignore_rain_sensor,'on')
            ''' process rain sensor '''
            if ignore_bool == True: #ignore the rain sensor
                raining = False

            return raining
        ''' end is_raining '''

        ''' Initialise for stop programs service call '''
        p_icon        = self._icon
        p_name        = self._name
        self._running = True
        self._stop    = False
        self._state   = True
        self.async_schedule_update_ha_state()
        step = 1

        _LOGGER.debug('-------------------- on execution: %s ----------------------------',self._name)
        _LOGGER.debug('Template: %s', self._template)
        if self._start_time is not None:
            _LOGGER.debug('Start Time %s: %s',self._start_time, self.hass.states.get(self._start_time))
        if self._irrigation_on is not None:
            _LOGGER.debug('Irrigation on %s: %s',self._irrigation_on, self.hass.states.get(self._irrigation_on))
        if self._run_freq is not None:
            _LOGGER.debug('Run Frequency %s: %s',self._run_freq, self.hass.states.get(self._run_freq))

        ''' if the zone has run update the last run attribute for the zone  '''
        state = await self.async_get_last_state()

        ''' zone loop to calculate the total run time '''
        self._total_runtime = 0
        zn = 0
        for zone in self._zones:
            z_rain_sen_v  = zone.get(ATTR_RAIN_SENSOR)
            z_ignore_v    = zone.get(ATTR_IGNORE_RAIN_SENSOR)
            z_water_v     = zone.get(ATTR_WATER)
            z_water_adj_v = zone.get(ATTR_WATER_ADJUST)
            z_wait_v      = zone.get(ATTR_WAIT)
            z_repeat_v    = zone.get(ATTR_REPEAT)
            z_name        = zone.get(CONF_NAME)
            z_run_freq    = zone.get(ATTR_RUN_FREQ)

            zn += 1

            ''' check if the zone should run '''
            if not self._triggered_manually:
                if z_run_freq is not None:
                    freq_obj = z_run_freq
                else:
                    if self._run_freq is not None:
                        freq_obj = self._run_freq
                if freq_obj is not None:
                    if should_run(freq_obj) == False:
                        continue
                if is_raining(z_rain_sen_v, z_ignore_v):
                    continue
                
            self._total_runtime += calculate_run_time(z_water_adj_v,z_water_v, z_wait_v, z_repeat_v).run_time
        ''' end of for zone loop to calculate total run time '''

        ''' Iterate through all the defined zones and run when required'''
        zn = 0
        for zone in self._zones:
            z_rain_sen_v  = zone.get(ATTR_RAIN_SENSOR)
            z_ignore_v    = zone.get(ATTR_IGNORE_RAIN_SENSOR)
            z_zone        = zone.get(ATTR_ZONE)
            z_water_v     = zone.get(ATTR_WATER)
            z_water_adj_v = zone.get(ATTR_WATER_ADJUST)
            z_wait_v      = zone.get(ATTR_WAIT)
            z_repeat_v    = zone.get(ATTR_REPEAT)
            z_icon        = zone.get(ATTR_ICON)
            z_name        = zone.get(CONF_NAME)
            z_ignore_bool = False
            update_run_date = False
            z_run_freq    = zone.get(ATTR_RUN_FREQ)
            zn += 1

            ''' stop the program if requested '''
            if self._stop == True:
                break

            if  z_ignore_v is not None and self.hass.states.async_available(z_ignore_v):
                _LOGGER.error('%s not found',z_ignore_v)
                continue #try next zone#
            if  z_water_v is not None and self.hass.states.async_available(z_water_v):
                _LOGGER.error('%s not found',z_water_v)
                continue #try next zone#
            if  z_water_adj_v is not None and self.hass.states.async_available(z_water_adj_v):
                _LOGGER.error('%s not found',z_water_adj_v)
                continue #try next zone#
            if  z_rain_sen_v is not None and self.hass.states.async_available(z_rain_sen_v):
                _LOGGER.error('%s not found',z_rain_sen_v)
                continue #try next zone#
            if  z_wait_v is not None and self.hass.states.async_available(z_wait_v):
                _LOGGER.error('%s not found',z_wait_v)
            if  z_repeat_v is not None and self.hass.states.async_available(z_repeat_v):
                _LOGGER.error('%s not found',z_repeat_v)

            ''' check if the zone should run '''
            if not self._triggered_manually:
                if z_run_freq is not None:
                    freq_obj = z_run_freq
                else:
                    if self._run_freq is not None:
                        freq_obj = self._run_freq
 
                if should_run(freq_obj) == False:
                    continue

                if is_raining(z_rain_sen_v, z_ignore_v):

                    ''' set the icon to Raining - for a few seconds '''
                    self._icon = self._rain_icon
                    self._name = self._program_name + "-" + z_name
                    self.async_schedule_update_ha_state()
                    await asyncio.sleep(5)
                    self._icon = p_icon
                    self._name = self._program_name
                    self.async_schedule_update_ha_state()
                    await asyncio.sleep(1)
                    continue #try next zone#

            ''' end if not run manually '''

            ''' stop the program if requested '''
            if self._stop == True:
                break

            if self._allow_multiple_zones == False:
                ''' stop all programs other this one when a new zone kicks in '''
                DATA = {'ignore': self._device_id}
                await self.hass.services.async_call(DOMAIN,
                                                    'stop_programs',
                                                    DATA)
                await asyncio.sleep(1)

            ''' factor to adjust watering time and calculate run time'''
            runtime = calculate_run_time(z_water_adj_v, z_water_v, z_wait_v, z_repeat_v)
            self._runtime = runtime.run_time
            z_water = runtime.water
            z_wait = runtime.wait
            z_repeat = runtime.repeat

            '''Set time remaining attribute '''
            self._ATTRS [ATTR_REMAINING] = format_run_time(self._total_runtime)
            setattr(self, '_state_attributes', self._ATTRS)

            ''' run the watering cycle, water/wait/repeat '''
            DATA = {ATTR_ENTITY_ID: z_zone}
            _LOGGER.debug('switch data:%s',DATA)
            for i in range(z_repeat, 0, -1):
                _LOGGER.debug('run switch repeat:%s',i)
                if self._stop == True:
                    break
                self._name = self._program_name + "-" + z_name
                if self.hass.states.is_state(z_zone,'off'):
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_ON,
                                                        DATA)

                self._icon = z_icon
                self.async_schedule_update_ha_state()

                water = z_water * 60
                for w in range(0,water, step):
                    self._total_runtime = self._total_runtime - step
                    self._ATTRS [ATTR_REMAINING] = format_run_time(self._total_runtime)
                    setattr(self, '_state_attributes', self._ATTRS)
                    self.async_schedule_update_ha_state()
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break

                if z_wait > 0 and i > 1 and not self._stop:
                    ''' Eco mode is enabled '''
                    self._icon = self._wait_icon
                    self.async_schedule_update_ha_state()
                    if self.hass.states.is_state(z_zone,'on'):
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_OFF,
                                                            DATA)

                    wait = z_wait * 60
                    for w in range(0,wait, step):
                        self._total_runtime = self._total_runtime - step
                        self._ATTRS [ATTR_REMAINING] = format_run_time(self._total_runtime)
                        setattr(self, '_state_attributes', self._ATTRS)
                        self.async_schedule_update_ha_state()
                        await asyncio.sleep(step)
                        if self._stop == True:
                            break

                ''' turn the switch entity off '''
                if i <= 1 or self._stop:

                    ''' last/only cycle '''
                    if self.hass.states.is_state(z_zone,'on'):
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_OFF,
                                                            DATA)
            ''' End of repeat loop '''
            if not self._stop and not self._triggered_manually:
                zonelastran = ('zone%s_%s' % (zn, ATTR_LAST_RAN))   
                self._ATTRS[zonelastran] = dt_util.now()
                setattr(self, '_state_attributes', self._ATTRS)
                self.async_schedule_update_ha_state()
        ''' end of for zone loop '''

        if not self._stop:
            self._ATTRS [ATTR_LAST_RAN] = dt_util.now()

        self._ATTRS [ATTR_REMAINING] = ('%d:%02d:%02d' % (0, 0, 0))
        setattr(self, '_state_attributes', self._ATTRS)

        self._state                 = False
        self._running               = False
        self._stop                  = False
        self._triggered_manually    = True
        self._icon                  = p_icon
        self._name                  = self._program_name

        self.async_write_ha_state()
        _LOGGER.debug('program run complete')


    async def async_turn_off(self, **kwargs):

        self._stop = True

        for zone in self._zones:
            z_zone = zone.get(ATTR_ZONE)
            DATA = {ATTR_ENTITY_ID: z_zone}
            _LOGGER.debug('Zone switch %s: %s',z_zone, self.hass.states.get(z_zone))
            if self.hass.states.is_state(z_zone,'on'):
                await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_OFF,
                                                    DATA)

        self._state = False
        self.async_schedule_update_ha_state()