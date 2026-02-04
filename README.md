# Safetec Water Home Assistant Custom Component (Version 1.4)

This repository provides a Home Assistant custom component that polls a Safetec water device and exposes sensors for:

- Total water volume (liters, `TOTAL_INCREASING` for statistics/consumption).
- Water consumption per hour (liters per hour, derived from total volume).
- Last tapped volume (liters).
- Single consumption volume (liters, converted from ml).
- Water pressure (bar, updated every 15 seconds).
- Water flow (liters per hour).
- Water temperature (°C).
- Battery voltage (V).
- DC/adapter voltage (V).
- Firmware version, serial number, conductivity, WiFi RSSI, IP address, default gateway, and valve status are exposed as attributes on each sensor.

## Installation

1. Copy the custom component into your Home Assistant `custom_components` directory:

   ```bash
   custom_components/
     safetec_water/
       __init__.py
       config_flow.py
       const.py
       manifest.json
       sensor.py
   ```

2. Restart Home Assistant.

## UI Configuration (Config Flow)

You can also add the integration from the Home Assistant UI:

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Safetec Water**.
3. Enter the device host and port.
4. (Optional) Open the integration options to change the host, port, or polling interval in seconds.
   - Minimum supported value: **5 seconds**.
   
This integration is configured **only** through the UI (no `configuration.yaml` settings).

## InfluxDB (optional, uses existing HA configuration)

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
- Firmware version, serial number, conductivity, WiFi RSSI, IP address, default gateway, and valve status are exposed as attributes on each sensor and added to the device registry.
- UI setup creates a config entry in Home Assistant storage and **does not** auto-write `configuration.yaml`.
