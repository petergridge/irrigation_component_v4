# Irrigation Component V4
The driver for this project is to provide an easy to configure user interface for the gardener of the house. The goal is that once the inital configuration is done all the features can be modified through lovelace cards. 

The provided working test harness is self contained with dummy switches and rain sensor that can be used to become familiar with the capabilities of the component and a sample of LoveLace configuration that uses the Entities card with conditions and the Conditions Card to simplify the UI.

![irrigation|690x469,50%](irrigation1.JPG) 
Image 1: All attributes rendered using the companion custom card

All the inputs of the platform are Home Assistant entities for example the start time is provided via a input_datetime entity. The information is evaluated to trigger the irrigation action according to the inputs provided.

Watering can occur in an Eco mode where a water/wait/repeat cycle is run to minimise run off by letting water soak as a by using several short watering cycles. The wait and repeat configuration is optional if you only want to water for a single lengthy period of time.

The rain sensor is implemented as a binary_sensor, this allows practically any combination of sensors to suspend the irrigation. 

Implemented as a switch you can start a program manually or using an automation.

Only one program can run at a time to prevent multiple solenoids being activated. If program start times result in an overlap the running program will be stopped.

Manually starting a program by turning the switch on will not evaluate the rain sensorany rules it will just run the shedule, as there is an assumption that there is an intent to run the program.

## INSTALLATION

### To create a working sample
* Copy the irrigationprogram folder to the ‘config/custom components/’ directory 
* Copy the 'irrigation.yaml' file to the packages directory or into configuration.yaml. Sample configuration
* Restart Home Assistant
* Install irrigation_custom_card from this repository TBA

### Important
* Make sure that all of the objects you reference i.e. input_boolean, switch etc are defined or you will get errors when the irrigationprogram is triggered. Check the log for errors.

### Pre-requisite
* The time_date integration is required
```yaml
sensor:
  - platform: time_date
    display_options:
      - 'time'
      - 'date'
```
### Debug
Add the following to your logger section configuration.yaml
```yaml
logger:
    default: warning
    logs:
        custom_components.irrigationprogram: debug
```
### Rain Sensor feature
If a rain sensor is not defined the zone will always run at the nominated start time.

If the irrigation program is run manually the rain sensor value is ignored and all zones will run.

The rain sensor can be optionally defined in each zone. You can:
* Define the same sensor for each zone 
* Have a different sensor for different areas
* Configure the ability to ignore the rain sensor

### Monitor Controller feature
If this binary sensor is defined it will not execute a schedule if the controller is offline. This is ideal for ESP Home implementations.

### Watering Adjuster feature
As an alternative to the rain sensor you can also use the watering adjustment. With this feature the integrator is responsible to provide the value using a input_number component. I imagine that this would be based on weather data or a moisture sensor.

See the https://github.com/petergridge/openweathremaphistory for a companion sensor that may be useful.

Setting *water_adjustment* attribute allows a factor to be applied to the watering time.

* If the factor is 0 no watering will occur
* If the factor is 0.5 watering will run for only half the configured watering time. Wait and repeat attributes are unaffected.

The following automation is an example of how the input_number.adjust_run_time could be maintained
```yaml
automation:
- id: '1553507967550'
  alias: rain adjuster
  mode: restart
  trigger:
  - platform: time_pattern
    minutes: "/1"
  action:
    - service: input_number.set_value
      entity_id: input_number.rain_adjuster
      data:
        value: "{{ value template calculation }}"
```

### Run Days and Run Frequency
Run frequency allows the definition of when the program will run.

This can be a specific set of days or the number of days between watering events. This can be defined at the Program or zone level. Application at the zone level allows different zones to execute at the same time but using varying frquencies. for example: Vege Patch every two days and the Lawn once a week.

* *Run Freq* allows the water to occur at a specified frequency, for example, every 3 days or only on Monday, Wednesday and Saturday. 
* *Run Days DEPRECATED*  in this version, if you used this in version 3 simply rename *Run Days* to *Run Freq* to retain the same behaviour.

Defining a selection list to use with the run_freq attribute.
```yaml
input_select:
  irrigation_freq:
    name: Zone1 Frequency
    options:
      - "1"
      - "2"
      - "3"
      - "4"
      - "5"
      - "6"
      - "7"
      - "['Wed','Sat']"
      - "['Sun','Thu']"
      - "['Mon','Fri']"
      - "['Tue','Sat']"
      - "['Sun','Wed']"
      - "['Mon','Thu']"
      - "['Tue','Fri']"
      - "['Mon','Wed','Fri']"
      - "['Mon','Tue','Wed','Thu','Fri','Sat','Sun']"
```

### ECO feature
The ECO feature allows multiple short watering cycles to be configure for a zone in the program to minimise run off and wastage. Setting the optional configuration of the Wait, Repeat attributes of a zone will enable the feature. 

* *wait* sets the length of time to wait between watering cycles
* *repeat* defines the number of watering cycles to run

## CONFIGURATION
### Example configuration.yaml entry
```yaml

  switch:
  - platform: irrigationprogram
    switches: 
      morning:
        name: Morning
        irrigation_on: input_boolean.irrigation_on
        start_time: input_datetime.irrigation_morning_start_time
        run_freq: input_select.irrigation_freq
        icon: mdi:fountain
        zones:
        # Adjust watering time used 
        # Watering time adjusted to water * adjust_watering_time
          - zone: switch.irrigation_solenoid_01
            name: Pot Plants
            water: input_number.irrigation_pot_plants_run
            water_adjustment: input_number.adjust_run_time
            wait: input_number.irrigation_pot_plants_wait
            repeat: input_number.irrigation_pot_plants_repeat
            icon: 'mdi:flower'
        # No rain sensor defined, will always water to the schedule
          - zone: switch.irrigation_solenoid_03
            name: Greenhouse
            water: input_number.irrigation_greenhouse_run
            wait: input_number.irrigation_greenhouse_wait
            repeat: input_number.irrigation_greenhouse_repeat
            icon: 'mdi:flower'
        # Rain sensor used, watering time only
          - zone: switch.irrigation_solenoid_02
            name: Front Lawn
            water: input_number.irrigation_lawn_run
            rain_sensor: binary_sensor.irrigation_rain_sensor
            ignore_rain_sensor: switch.ignore_rain_sensor

    # minimal configuration, will run everyday at the time specified
      afternoon:
        name: Afternoon
        start_time: input_datetime.irrigation_afternoon_start_time
        zones:
          - zone: switch.irrigation_solenoid_01
            name: Pot Plants
            water: input_number.irrigation_pot_plants_run
          - zone: switch.irrigation_solenoid_02
            name: Front Lawn
            water: input_number.irrigation_lawn_run
```
## CONFIGURATION VARIABLES

## program
*(string)(Required)* the switch entity.
>#### name
*(string)(Optional)* display name for the irrigation program switch.
>#### start_time
*(input_datetime)(Required)* the local time for the program to start.
>#### run_freq 
*(input_select)(optional)* A numeric value that represent the frequency to water, 1 is daily, 2 is every second day and so on. If not provided will run every day.
>#### irrigation_on
*(input_boolean)(Optional)* Attribute to temporarily disable the watering schedule
>#### icon
*(icon)(Optional)* The icon displayed for the program. (default: mdi:fountain)
>#### unique_id
*(string)(Optional)* An ID that uniquely identifies this switch. Set this to an unique value to allow customisation trough the UI.
>#### Zones 
*(list)(Required)* The list of zones to water.
>>#### zone
*(entity)(Required)* This is the switch that represents the solenoid to be triggered.
>>#### name
*(string)(Required)* This is the name displayed when the zone is active.
>>#### rain_sensor
*(binary_sensor)(Optional)* A binary sensor - True or On will prevent the irrigation starting. e.g. rain sensor, greenhouse moisture sensor or template sensor that checks the weather
>>#### ignore_rain_sensor
*(input_boolean)(Optional)* Attribute to allow the zone to run regardless of the state of the rain sensor. Useful for a greenhouse zone that never gets rain.
>>#### water
*(input_number)(Required)* This it the period that the zone will turn the switch_entity on for.
>>#### water_adjustment
*(input_number)(Optional)* This is a factor to apply to the watering time that can be used as an alternative to using a rain sensor. The watering time will be multiplied by this factor to adjust the run time of the zone.
>>#### wait
*(input_number)(Optional)* This provides for an Eco capability implementing a cycle of water/wait/repeat to allow water to soak into the soil.
>>#### repeat
*(input_number)(Optional)* This is the number of cycles to run water/wait/repeat.
>>#### run_freq 
*(input_select)(optional)* A numeric value that represent the frequency to water, 1 is daily, 2 is every second day and so on. If not provided will run every day.
>> #### icon
*(icon)(Optional)* This will replace the default mdi:water icon shown when the zone is running.

## SERVICES
```yaml
irrigationprogram.stop_programs:
    description: Stop any running program.
```

## REVISION HISTORY
### 4.0 
* New repository for version 4 with improvements and support for custom card delivery
* Allow definition for run frequency at the zone level
* DEPRICATE the run days attribute. Simply rename this attribute to run_freq to maintain the change
* Expose attributes to support the new custom card

### 3.0.3
* Update to validate the referenced objects after HASS has started.

### 3.0.2
* Update to fix bug in last run date attribute. Impacted Programs that run on the Frequency option.

### 3.0.0
* BREAKING CHANGE: deprecate the irrigationzone component
* Move zone details into the irrigationprogram component - feature request
* Move rain sensor to the zone definition - feature request 
* Move ignore rain sensor into the zone definition - feature request
* Improve validation of components to warn when HA objects are not found
* Add run time adjustment - feature request
* improved async behavior when automatically starting the program

### 1.1.0 
* add version to manifest.json files
* tweak how the program turns off zones
* remove validation for time.sensor

### 0.2
•            Remove requirement for HA time sensor
