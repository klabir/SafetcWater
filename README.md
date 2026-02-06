# Safetec Water Home Assistant Custom Component (Version 1.5)

This repository provides a Home Assistant custom component that polls a Safetec water device and exposes sensors for:

- Total water volume (liters, `TOTAL_INCREASING` for statistics/consumption).
- Water consumption per hour (liters, derived from the total volume since the top of the current hour).
- Last tapped volume (liters).
- Single consumption volume (liters, converted from ml).
- Water pressure (bar, updated every configured scan interval; default 15 seconds).
- Water flow (liters per hour).
- Water temperature (°C).
- Water hardness (°dH, derived from conductivity).
- WiFi state.
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

## HACS Installation (recommended)

1. In HACS, add this repository as a custom repository (Integration).
2. Install **Safetec Water** from HACS.
3. Restart Home Assistant.

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
- All device API calls (main + pressure endpoints) use the same configurable scan interval from integration options (default: 15 seconds, minimum: 5 seconds).
- Main data is fetched via `/trio/get/all` with fallback to individual endpoints and bounded retries for better stability.
- The per-hour consumption sensor reports the delta from the total volume at the start of the current hour and resets to zero on the hour.
- Pressure is stored as bar with three decimal places.
- Temperature is `get/cel` divided by 10 (°C).
- Battery and DC voltage are `get/bat` and `get/net` divided by 10 (V).
- Firmware version, serial number, conductivity, WiFi RSSI, WiFi state, IP address, default gateway, and valve status are exposed as attributes on each sensor and added to the device registry.
- UI setup creates a config entry in Home Assistant storage and **does not** auto-write `configuration.yaml`.
