# Irrigation Component V4 <img src="https://github.com/petergridge/irrigation_component_v4/blob/main/icon.png" alt="drawing" width="75"/>

### Latest Changes V4.0.14
* Bug Fixes
* Add inter zone delay to provide a delay between zones starting.
* Add zone grouping to allow groups of zones to run concurrently. 
* Requires Custom Card version 4.0.12
* Breaking change:
* DEPRECATED *icon* attributes
* DEPRECATED *allow_multiple* option as this is replaced by zone groups.

This release sees the delivery of a **custom card https://github.com/petergridge/irrigation_card** to render the program options specified in the configuration.

The driver for this project is to provide an easy to configure user interface for the gardener of the house. The goal is that once the inital configuration is done all the features can be modified using the custom lovelace card.

This program is essentially a scheduling tool, one user has also used this to schedule the running of his lawn mower, so the use is far broader than I anticipated.

The provided working test harness is self contained with dummy switches and rain sensor that can be used to become familiar with the capabilities of the component.

![irrigation|690x469,50%](irrigation1.JPG) 
**Image 1:** All attributes rendered using the companion custom card

All the inputs of the platform are Home Assistant helpers for example the start time is provided via a input_datetime. 

The information provided by the configuraton is evaluated to trigger the irrigation action according to the inputs provided.

Watering can occur in an ECO mode where a water/wait/repeat cycle is run to minimise run off by letting water soak in using several short watering cycles. The wait and repeat configuration is optional.

The rain sensor is implemented as a binary_sensor, this allows practically any combination of sensors to suspend the irrigation. This can be defined at the zone level to allow for covered areas to continue watering while exposed areas are suspended.

Implemented as a switch, you can start a program using the schedule, manually or using an automation. Manually starting a program by turning the switch on will not evaluate the rain sensor rules it will just run the program, as there is an assumption that there is an intent to run the program regardless of sensors.

Only one program can run at a time by default to prevent multiple solenoids being activated. If program start times result in an overlap the running program will be stopped. Zones can be configured to run concurrently or sequentially.

## INSTALLATION

### To create a working sample
* Copy the custom_components/irrigationprogram folder to the ‘config/custom components/’ directory
* Restart Home Assistant
* Copy the 'irrigationtest.yaml' file to the packages directory or into configuration.yaml
* Restart Home Assistant
* Install irrigation_custom_card from this repository **https://github.com/petergridge/irrigation_card**
* Follow the custom card instructions to add a card for each of: switch.morning, switch.afternoon and switch.night

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

### Time or Volume based watering
You can define a 'flow sensor' that provides a volume/minute rate. eg litres per minute. Once defied the 'water' attribute will be read as volume eg 15 litres not 15 minutes.

This example is for a zone that has been defined with a flow sensor
```yaml
zones:
  - zone: switch.zone_1
    name: Lawn
    water: input_number.irrigation_lawn_water
    flow_sensor: sensor.irrigation_flow_sensor
    zone_group: input_text.zone1_group
```

### Zone Group
You can optionally group zones to run concurrently or sequentially. Inputs are from an input_text or input_select helper defined for each zone. Blank groups or where a zone_group is not defined will be sequential zones. Zones are grouped by having the same text value, for example each zone with a value of 'A' will run concurrently.

```
zones:
  - zone: switch.zone_1
    name: Lawn
    water: input_number.irrigation_lawn_water
    zone_group: input_text.zone1_group
```

### Monitor Controller feature
If this binary sensor is defined it will not execute a schedule if the controller is offline. This is ideal for ESP Home implementations.

### Watering Adjuster feature
As an alternative to the rain sensor you can also use the watering adjustment. With this feature the integrator is responsible to provide the value using a input_number component. I imagine that this would be based on weather data or a moisture sensor.

See the **https://github.com/petergridge/openweathremaphistory** for a companion custom sensor that may be useful.

Setting *water_adjustment* attribute allows a factor to be applied to the watering time.

* If the factor is 0 no watering will occur
* If the factor is 0.5 watering will run for only half the configured watering time/volume. Wait and repeat attributes are unaffected.
* A factor of 1.1 could also be used to apply 10% more water if required.

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

This can be a specific set of days or the number of days between watering events. This can be defined at the Program or zone level. Application at the zone level allows different zones to execute at the same time but using varying frequencies. for example: Vege Patch every two days and the Lawn once a week.

* *Run Freq* allows the water to occur at a specified frequency, for example, every 3 days or only on Monday, Wednesday and Saturday. 

Defining a selection list to use with the run_freq attribute, remove the options you don't want to use.
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

A self contained working sample configuration is provided in the packages directory of this repository.

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
        inter_zone_delay: input_number.inter_zone_delay
        zones:
        # Watering time adjusted to water * adjust_watering_time
          - zone: switch.irrigation_solenoid_01
            name: Pot Plants
            water: input_number.irrigation_pot_plants_run
            water_adjustment: input_number.adjust_run_time
            wait: input_number.irrigation_pot_plants_wait
            repeat: input_number.irrigation_pot_plants_repeat
            zone_group: input_text.zone1_group
            enable_zone: input_boolean.enable_zone1
        # No rain sensor defined, will always water to the schedule
          - zone: switch.irrigation_solenoid_03
            name: Greenhouse
            water: input_number.irrigation_greenhouse_run
            zone_group: input_text.zone2_group
            enable_zone: input_boolean.enable_zone2
        # Rain sensor used, watering time only
          - zone: switch.irrigation_solenoid_02
            name: Front Lawn
            water: input_number.irrigation_lawn_run
            rain_sensor: binary_sensor.irrigation_rain_sensor
            ignore_rain_sensor: switch.ignore_rain_sensor
            zone_group: input_text.zone3_group
            enable_zone: input_boolean.enable_zone3

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
|Attribute       |Type   |Mandatory|Description|
|:---            |:---   |:---     |:---       |
|program         |string |Required |Name of the switch, exposed as switch.program|
|&nbsp;&nbsp;&nbsp;&nbsp;start_time|input_datetime |Required|The local time for the program to start|
|&nbsp;&nbsp;&nbsp;&nbsp;name|string|Optional|Display name for the irrigation program switch|
|&nbsp;&nbsp;&nbsp;&nbsp;show_config|input_boolean|Optional|Attribute to support hiding the configuration detail in the custom card |
|&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select   |Optional|Indicate how often to run. If not provided will run every day|
|&nbsp;&nbsp;&nbsp;&nbsp;[controller_monitor](#monitor-controller-feature)|binary_sensor  |Optional|Detect if the irrigation controller is online. Schedule will not execute if offline|
|&nbsp;&nbsp;&nbsp;&nbsp;irrigation_on|input_boolean  |Optional|Attribute to temporarily disable the watering schedule|
|&nbsp;&nbsp;&nbsp;&nbsp;inter_zone_delay|input_number   |Optional|Delays the start of each zone by the specified number of seconds|
|&nbsp;&nbsp;&nbsp;&nbsp;zones|list|Required|List of zones to run|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&nbsp;zone|switch|Required|This is the switch that represents the solenoid to be triggered|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;name|string|Required|This is the name displayed when the zone is active|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;water|input_number|Required|The period that the zone will turn the switch_entity on for|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[water_adjustment](#water-adjustment-feature)|sensor, input_number|Optional|A factor,applied to the watering time to decrease or increase the watering time|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[wait](#eco-feature)|input_number|Optional|Wait time of the water/wait/repeat ECO option|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[repeat](#eco-feature)|input_number|Optional|The number of cycles to run water/wait/repeat|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[flow_sensor](#time-or-volume-based-watering)|sensor|Optional|Provides flow rate per minute. The water value will now be assessed as volume|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[rain_sensor](#rain-sensor-feature)|binary_sensor  |Optional|True or On will prevent the irrigation starting|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;ignore_rain_sensor|input_boolean|Optional|Attribute to allow the zone to run regardless of the state of the rain sensor|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[zone_group](#zone-group)|input_select, input_text|Optional|Allow multiple zones to be active at the same time|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;[run_freq](#run-days-and-run-frequency)|input_select|Optional|Indicate how often to run. If not provided will run every day|
|&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;enable_zone|input_boolean|Optional|Disable a zone, preventing it from running in either manual or scheduled executions|

## SERVICES
```yaml
irrigationprogram.stop_programs:
    description: Stop any running program.
```

## REVISION HISTORY
### 4.0.14
* Start stop fix.
* remaining time fix
### 4.0.13
* Group execution fix.
### 4.0.12
* Add inter zone delay to provide a delay between zones starting.
* Add zone grouping to allow groups of zones to run concurrently. 
* Requires Custom Card version 4.0.12
* Breaking change:
* DEPRECATED *icon* attributes
* DEPRECATED *allow_multiple* option as this is replaced by zone groups.
### 4.0.11
* Provide an enable_zone option to allow a more intuitive presentation in the Custom Card. Requires Custom Card version 4.0.11
### 4.0.10
* Add volume based watering option. Water can occur using a flow meter instead of based on time
* Add capability to turn on a pump or other switch when starting a zone
* fix error in remaining time presentation
### 4.0.8
* implement support for hiding configuration in the custom card
### 4.0.7
* fix issue with new installations
### 4.0.6
* Add run zone button to the custom card
### 4.0.5
* Add ability to disable a zone
* Handling new and changes zones to an existing program
* Move zone operations to a class
* provide zone level remaining time for the custom card
* improve start time handling
### 4.0.3
* corrected error on new program definition

### 4.0.2
* Enable both input number and sensor for water adjustment
* Refactor rain sensor handling

### 4.0.1
* Correct time remaining calculation

### 4.0.0
* New repository for Version 4 with improvements and support for custom card support
* Allow definition for run frequency at the zone level - feature request
* DEPRECATED the *run_days* attribute. Simply rename this attribute to *run_freq* to maintain the functionality
* Optionally allow multiple programs to run simultaneously use *allow_multiple* config option
* Allow monitoring of the irrigation controller hardware if supported, will not run schedule if controller is offline
