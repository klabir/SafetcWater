# Safetec Water Home Assistant Custom Component (Version 1.1)

## Summary (Version 1.1)

- Polls Safetec Water device endpoints every minute to expose volume, pressure, temperature, voltages, and diagnostics in Home Assistant.
- Reports total volume as `TOTAL_INCREASING` for consumption statistics and InfluxDB storage.
- Converts raw device units to human-friendly values (bar, °C, V) and surfaces firmware/serial as diagnostics.

This repository provides a Home Assistant custom component that polls a Safetec water device and exposes sensors for:

- Total water volume (liters, `TOTAL_INCREASING` for statistics/consumption).
- Water pressure (bar, updated every minute).
- Water temperature (°C).
- Battery voltage (V).
- DC/adapter voltage (V).
- Firmware version (diagnostic).
- Serial number (diagnostic).

## Installation

1. Copy the custom component into your Home Assistant `custom_components` directory:

   ```bash
   custom_components/
     safetec_water/
       __init__.py
       const.py
       manifest.json
       sensor.py
   ```

2. Restart Home Assistant.

## Configuration (`configuration.yaml`)

Add the Safetec Water platform configuration and point it at your device IP address:

```yaml
sensor:
  - platform: safetec_water
    host: 192.168.1.94
    port: 5333
```

### InfluxDB (optional, uses existing HA configuration)

If you already have InfluxDB configured, Home Assistant will store these sensors in that database automatically. Example:

```yaml
influxdb:
  host: 0.0.0.0
  port: 8086
  database: homeassistant_influx_db
  username: homeassistant_user
  password: ""
```

## Notes

- Total volume is reported as `TOTAL_INCREASING`, so Home Assistant can calculate usage per hour/day/week/month using statistics.
- Pressure is stored as bar with three decimal places.
- Temperature is `get/cel` divided by 10 (°C).
- Battery and DC voltage are `get/bat` and `get/net` divided by 10 (V).
- Firmware version and serial number are exposed as diagnostic sensors and added to the device registry.
