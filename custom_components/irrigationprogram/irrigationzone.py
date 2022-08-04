import logging
import asyncio
import voluptuous as vol
from datetime import timedelta
from time import sleep
import math
import homeassistant.util.dt as dt_util

from .const import (
    ATTR_RUN_FREQ,
    ATTR_RAIN_SENSOR,
    CONST_SWITCH,
    ATTR_IGNORE_RAIN_SENSOR,
    ATTR_ZONE,
    ATTR_PUMP,
    ATTR_FLOW_SENSOR,
    ATTR_WATER,
    ATTR_WAIT,
    ATTR_REPEAT,
    ATTR_DISABLE_ZONE,
    ATTR_ENABLE_ZONE,
    ATTR_WATER_ADJUST,
)

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ATTR_ICON,
    CONF_NAME,
)

_LOGGER = logging.getLogger(__name__)

class irrigationzone:

    def __init__(
        self,
        hass,
        zone_data,
        p_run_freq,
    ):
        self.hass                = hass
        self._name               = zone_data.get(CONF_NAME)
        self._switch             = zone_data.get(ATTR_ZONE)
        self._pump               = zone_data.get(ATTR_PUMP)
        self._run_freq           = zone_data.get(ATTR_RUN_FREQ,p_run_freq)
        self._icon               = zone_data.get(ATTR_ICON)
        self._rain_sensor        = zone_data.get(ATTR_RAIN_SENSOR)
        self._ignore_rain_sensor = zone_data.get(ATTR_IGNORE_RAIN_SENSOR)
        self._disable_zone       = zone_data.get(ATTR_DISABLE_ZONE)
        self._enable_zone        = zone_data.get(ATTR_ENABLE_ZONE)

        
        self._flow_sensor        = zone_data.get(ATTR_FLOW_SENSOR)
        self._water              = zone_data.get(ATTR_WATER)
        self._water_adjust       = zone_data.get(ATTR_WATER_ADJUST)
        self._wait               = zone_data.get(ATTR_WAIT)
        self._repeat             = zone_data.get(ATTR_REPEAT)

        self._last_run           = None
        self._run_time           = 0
        self._default_run_time   = 0
        self._remaining_time     = 0
        self._state              = 'off'
        self._stop               = False

 
    def name(self):
        '''Return the name of the variable.'''
        return self._name

    def icon(self):
        '''Return the name of the variable.'''
        return self._icon

    def switch(self):
        return self._switch

    def pump(self):
        return self._pump

    def run_freq(self):
        return self._run_freq
    def run_freq_value(self):
        self._run_freq_value = None
        if self._run_freq is not None:
            if  self.hass.states.get(self._run_freq) == None:
                _LOGGER.warning('run_freq: %s not found, check your configuration',self._run_freq)
            else:
                self._run_freq_value = self.hass.states.get(self._run_freq).state
        else:
            self._run_freq_value = None
    
        return self._run_freq_value

    def rain_sensor(self):
        return self._rain_sensor
    def rain_sensor_value(self):
        self._rain_sensor_value = False
        if self._rain_sensor is not None:
            if  self.hass.states.get(self._rain_sensor) == None:
                _LOGGER.warning('rain sensor: %s not found, check your configuration',self._rain_sensor)
            else:
                self._rain_sensor_value = self.hass.states.is_state(self._rain_sensor,'on')
        else:
            self._rain_sensor_value = False
        return self._rain_sensor_value

    def ignore_rain_sensor(self):
        return self._ignore_rain_sensor
    def ignore_rain_sensor_value(self):
        self._ignore_rain_sensor_value = False
        if  self._ignore_rain_sensor is not None:
            if  self.hass.states.get(self._ignore_rain_sensor) == None:
                _LOGGER.warning('Ignore rain sensor: %s not found, check your configuration',self._ignore_rain_sensor)
            else:
                 self._ignore_rain_sensor_value = self.hass.states.is_state(self._ignore_rain_sensor,'on')
        return self._ignore_rain_sensor_value

    def water_adjust(self):
        return self._water_adjust
    def water_adjust_value(self):
        z_water_adj = 1
        try:
            if self._water_adjust is not None:
                z_water_adj = float(self.hass.states.get(self._water_adjust).state)
        except:
            _LOGGER.error('watering adjustment factor is not numeric %s', self._water_adjust)
        self._water_adjust_value = z_water_adj
        return self._water_adjust_value

    def flow_sensor(self):
        return self._flow_sensor
    def flow_sensor_value(self):
        if self._flow_sensor is not None:
            self._flow_sensor_value = int(float(self.hass.states.get(self._flow_sensor).state))
            return self._flow_sensor_value

    def water(self):
        return self._water
    def water_value(self):
        self._water_value = int(float(self.hass.states.get(self._water).state))
        return self._water_value

    def wait(self):
        return self._wait
    def wait_value(self):
        z_wait = 0
        try:
            if self._wait is not None:
                z_wait = int(float(self.hass.states.get(self._wait).state))
        except:
            _LOGGER.error('wait is not numeric %s', self._wait)
        self._wait_value = z_wait
        return self._wait_value

    def repeat(self):
        return self._repeat
    def repeat_value(self):
        z_repeat = 1
        try:
            if self._repeat is not None :
                z_repeat = int(float(self.hass.states.get(self._repeat).state))
                if z_repeat == 0:
                    z_repeat = 1
        except:
            _LOGGER.error('repeat is not numeric %s', self._repeat)
        self._repeat_value = z_repeat
        return self._repeat_value

    def state(self):
        return self._state

    def disable_zone(self):
        return self._disable_zone

    def disable_zone_value(self):
        self._disable_zone_value = False
        
        try:
            if self._disable_zone is not None:
                self._disable_zone_value = self.hass.states.is_state(self._disable_zone,'on')
        except:
            pass
        
        try:
            if self._enable_zone is not None:
                self._disable_zone_value = self.hass.states.is_state(self._enable_zone,'off')
        except:
            pass
        return self._disable_zone_value

    def enable_zone(self):
        return self._enable_zone

    def enable_zone_value(self):
        self._enable_zone_value = False
        try:
            if self._enable_zone is not None:
                self._enable_zone_value = self.hass.states.is_state(self._enable_zone,'on')
        except:
            pass
        return self._enable_zone_value

    def remaining_time(self):
        ''' remaining time or remaining volume '''
        return self._remaining_time

    def run_time(self):
        ''' update the run time component '''
        if self._flow_sensor is not None:
            z_water = math.ceil(int(float(self.water_value()) * float(self.water_adjust_value())))
            self._run_time = z_water  * self.repeat_value()
        else:
            z_water = math.ceil(int(float(self.water_value()) * float(self.water_adjust_value())))
            self._run_time = (((z_water + self.wait_value()) * self.repeat_value()) - self.wait_value()) * 60

        ''' zone has been disabled '''
        if self.disable_zone_value() == True:
            self._run_time = 0

        return self._run_time

    def last_run(self):
        return self._last_run

    def is_raining(self):
        ''' assess the rain_sensor including ignore rain_sensor'''
        if self.ignore_rain_sensor_value():
            return False
        else:  
            return self.rain_sensor_value()

    def should_run(self):
        try:
            ''' run if within 10 minutes of the start time '''
            calc_freq = float(((dt_util.as_timestamp(dt_util.now()) - dt_util.as_timestamp(self._last_run)) + 600) / 86400)
        except:
            ''' default to 10 days ago for new zones '''
            calc_freq = (dt_util.as_timestamp(dt_util.now()) - dt_util.as_timestamp(dt_util.now() - timedelta(days=10))) / 86400
            z_last_ran = dt_util.now() - timedelta(days=10)
            self._ATTRS [a] = z_last_ran
      
        Numeric_Freq = None
        String_Freq = None
        response = True
        try:
            Numeric_Freq = float(int(self.run_freq_value()))
        except:
            String_Freq = self.run_freq_value()
            ''' check if this day matches frequency '''
        if Numeric_Freq is not None:
            ''' provide a 10 minute threshold for the start time '''
            if Numeric_Freq <= calc_freq:
                response = True
            else:
                response =  False
        if String_Freq is not None:
            if dt_util.now().strftime('%a') not in String_Freq:
                response =  False
            else:
                response =  True

        return response
    ''' end should_run '''

    async def async_turn_on(self, **kwargs):
        ''' Watering time or volume to water
        
            water wait repeat cycle using either volume of time
            remaining is volume or time
        '''

        step = 1
        self._stop = False
        z_initial_volume = self.flow_sensor_value()
        z_water = self.water_value()
        z_wait = self.wait_value()
        z_repeat = self.repeat_value()
        self._remaining_time = self.run_time()
        ''' run the watering cycle, water/wait/repeat '''
        SOLENOID = {ATTR_ENTITY_ID: self._switch}
        if self._pump is not None:
            PUMP = {ATTR_ENTITY_ID: self._pump}
        for i in range(z_repeat, 0, -1):
            if self._stop == True:
                break

            self._state = 'on'
            if self.hass.states.is_state(self._switch,'off'):
                await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_ON,
                                                    SOLENOID)
                if self._pump is not None:
                    await self.hass.services.async_call(CONST_SWITCH,
                                                    SERVICE_TURN_ON,
                                                    PUMP)

            if self._flow_sensor is not None:
                ''' calculate the remaining volume '''
                water = z_water
                while water > 0:
                    #self._remaining_time -= self.flow_sensor_value()/(60/step)
                    water -= self.flow_sensor_value()/(60/step)
                    self._remaining_time = water/self.flow_sensor_value()*60
                    if self._remaining_time < 0:
                        self._remaining_time = 0
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break                    
            else: 
                ''' calculate remaining time '''
                water = z_water * 60
                for w in range(0,water, step):
                    self._remaining_time -= step
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break

            if z_wait > 0 and i > 1 and not self._stop:
                ''' Eco mode is enabled '''
                self._state = 'eco'
                if self.hass.states.is_state(self._switch,'on'):
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_OFF,
                                                        SOLENOID)
                    if self._pump is not None:
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_OFF,
                                                            PUMP)
                wait = z_wait * 60
                for w in range(0,wait, step):
                    if self._flow_sensor is None:
                        self._remaining_time -= step
                    await asyncio.sleep(step)
                    if self._stop == True:
                        break

            ''' turn the switch entity off '''
            if i <= 1 or self._stop:
                ''' last/only cycle '''
                self._remaining_time = 0
                
                if self.hass.states.is_state(self._switch,'on'):
                    await self.hass.services.async_call(CONST_SWITCH,
                                                        SERVICE_TURN_OFF,
                                                        SOLENOID)
                    if self._pump is not None:
                        await self.hass.services.async_call(CONST_SWITCH,
                                                            SERVICE_TURN_OFF,
                                                            PUMP)
        ''' End of repeat loop '''
        self._state = 'off'
 
        if not self._stop:
            return True
        else:
            return False


    async def async_turn_off(self, **kwargs):
        self._stop = True

        SOLENOID = {ATTR_ENTITY_ID: self._switch}
        await self.hass.services.async_call(CONST_SWITCH,
                                            SERVICE_TURN_OFF,
                                            SOLENOID)
        if self._pump is not None:
            PUMP = {ATTR_ENTITY_ID: self._pump}
            await self.hass.services.async_call(CONST_SWITCH,
                                                SERVICE_TURN_OFF,
                                                PUMP)

    def set_last_ran(self, p_last_ran):
        if p_last_ran is None:
            ''' default to 10 days ago for new zones '''
            self._last_run = dt_util.now() - timedelta(days=10)
        else:
            self._last_run = p_last_ran

    def validate(self, **kwargs):
        valid = True
        if  self._switch is not None and self.hass.states.async_available(self._switch):
            _LOGGER.error('%s not found',self._switch)
            valid = False
        if  self._water is not None and self.hass.states.async_available(self._water):
            _LOGGER.error('%s not found',self._water)
            valid = False
        if  self._wait is not None and self.hass.states.async_available(self._wait):
            _LOGGER.error('%s not found',self._wait)
            valid = False
        if  self._repeat is not None and self.hass.states.async_available(self._repeat):
            _LOGGER.error('%s not found',self._repeat)
            valid = False
        if  self._run_freq is not None and self.hass.states.async_available(self._run_freq):
            _LOGGER.error('%s not found',self._run_freq)
            valid = False
        if  self._rain_sensor is not None and self.hass.states.async_available(self._rain_sensor):
            _LOGGER.error('%s not found',self._rain_sensor)
            valid = False
        if  self._ignore_rain_sensor is not None and self.hass.states.async_available(self._ignore_rain_sensor):
            _LOGGER.error('%s not found',self._ignore_rain_sensor)
            valid = False
        if  self._disable_zone is not None and self.hass.states.async_available(self._disable_zone):
            _LOGGER.error('%s not found',self._disable_zone)
            valid = False
        if  self._enable_zone is not None and self.hass.states.async_available(self._enable_zone):
            _LOGGER.error('%s not found',self._enable_zone)
            valid = False
 
        return valid
