"""Safetec Water sensors."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

import aiohttp
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DEFAULT_PORT, DEFAULT_SCAN_INTERVAL, DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 0.5


class VolumePerHourTracker:
    """Track volume delta since the top of the current hour."""

    def __init__(self) -> None:
        self._hour_start: datetime | None = None
        self._hour_start_value: float | None = None

    def update(self, value: float | None) -> float | None:
        if value is None:
            return None
        now = dt_util.utcnow()
        current_hour = now.replace(minute=0, second=0, microsecond=0)
        if self._hour_start != current_hour or self._hour_start_value is None:
            self._hour_start = current_hour
            self._hour_start_value = value
            return 0.0
        delta = value - self._hour_start_value
        if delta < 0:
            return None
        return round(delta, 3)


@dataclass(frozen=True, kw_only=True)
class SafetecWaterSensorDescription(SensorEntityDescription):
    """Describes a Safetec Water sensor."""

    value_fn: Callable[[Any], Any] | None = None
    force_update: bool = False


WIFI_STATE_MAP = {
    "0": "Not connected",
    "1": "Connecting",
    "2": "Connected",
}

MAIN_KEY_MAP: dict[str, tuple[str, str]] = {
    "volume": ("get/vol", "getVOL"),
    "ltv": ("get/ltv", "getLTV"),
    "avo": ("get/avo", "getAVO"),
    "cnd": ("get/cnd", "getCND"),
    "flo": ("get/flo", "getFLO"),
    "temperature": ("get/cel", "getCEL"),
    "battery": ("get/bat", "getBAT"),
    "net": ("get/net", "getNET"),
    "wfr": ("get/wfr", "getWFR"),
    "wfs": ("get/wfs", "getWFS"),
    "wip": ("get/wip", "getWIP"),
    "wgw": ("get/wgw", "getWGW"),
    "vlv": ("get/vlv", "getVLV"),
    "firmware": ("get/ver", "getVER"),
    "serial": ("get/srn", "getSRN"),
}


class SafetecWaterClient:
    """Client for Safetec Water API."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}/trio"

    async def _async_get_json(self, path: str) -> dict[str, Any] | Any:
        url = f"{self._base_url}/{path}"
        last_error: Exception | None = None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                async with asyncio.timeout(10):
                    async with self._session.get(url) as response:
                        response.raise_for_status()
                        return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                last_error = err
                if attempt == RETRY_ATTEMPTS:
                    break
                wait_time = RETRY_BASE_DELAY_SECONDS * attempt
                _LOGGER.debug(
                    "Request failed (%s), retrying %s/%s in %.1fs: %s",
                    url,
                    attempt,
                    RETRY_ATTEMPTS,
                    wait_time,
                    err,
                )
                await asyncio.sleep(wait_time)

        raise UpdateFailed(f"Error fetching {url}: {last_error}") from last_error

    async def _async_fire_and_forget(self, path: str) -> None:
        url = f"{self._base_url}/{path}"
        try:
            async with asyncio.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

    async def async_fetch_main(self) -> dict[str, Any]:
        await self._async_fire_and_forget("set/adm/(2)f")

        all_payload: dict[str, Any] | Any | None = None
        try:
            all_payload = await self._async_get_json("get/all")
        except UpdateFailed as err:
            _LOGGER.debug("get/all failed, falling back to individual endpoints: %s", err)

        if isinstance(all_payload, dict):
            parsed = self._parse_main_payload(all_payload)
            if any(parsed.get(key) is not None for key in ("volume", "temperature", "battery")):
                return parsed

        return await self._async_fetch_main_individual()

    async def _async_fetch_main_individual(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for logical_key, (path, api_key) in MAIN_KEY_MAP.items():
            payload = await self._async_get_json(path)
            data[logical_key] = _normalize_api_value(_extract_value(payload, api_key))
        return self._coerce_main_data(data)

    def _parse_main_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for logical_key, (_, api_key) in MAIN_KEY_MAP.items():
            data[logical_key] = _normalize_api_value(_extract_value(payload, api_key))
        return self._coerce_main_data(data)

    def _coerce_main_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "volume": _coerce_number(data.get("volume")),
            "ltv": _coerce_number(data.get("ltv")),
            "avo": _coerce_number(data.get("avo")),
            "cnd": _coerce_number(data.get("cnd")),
            "flo": _coerce_number(data.get("flo")),
            "temperature": _coerce_number(data.get("temperature")),
            "battery": _coerce_number(data.get("battery")),
            "net": _coerce_number(data.get("net")),
            "wfr": _coerce_number(data.get("wfr")),
            "wfs": data.get("wfs"),
            "wip": data.get("wip"),
            "wgw": data.get("wgw"),
            "vlv": _coerce_number(data.get("vlv")),
            "firmware": data.get("firmware"),
            "serial": data.get("serial"),
        }

    async def async_fetch_pressure(self) -> dict[str, Any]:
        payload = await self._async_get_json("get/bar")
        pressure = _normalize_api_value(_extract_value(payload, "getBAR"))
        return {"pressure": _coerce_number(pressure)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Safetec Water sensors from a config entry."""
    await _async_setup_entities(
        hass,
        async_add_entities,
        host=entry.options.get(CONF_HOST, entry.data[CONF_HOST]),
        port=entry.options.get(CONF_PORT, entry.data.get(CONF_PORT, DEFAULT_PORT)),
        scan_interval=timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )


async def _async_setup_entities(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    *,
    host: str,
    port: int,
    scan_interval: timedelta,
) -> None:
    _LOGGER.debug(
        "Setting up Safetec Water v%s for host=%s port=%s",
        INTEGRATION_VERSION,
        host,
        port,
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = SafetecWaterClient(session, host, port)

    volume_tracker = VolumePerHourTracker()

    async def _update_main() -> dict[str, Any]:
        data = await client.async_fetch_main()
        data["volume_per_hour"] = volume_tracker.update(data.get("volume"))
        return data

    main_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Safetec Water",
        update_method=_update_main,
        update_interval=scan_interval,
    )
    pressure_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Safetec Water Pressure",
        update_method=client.async_fetch_pressure,
        update_interval=scan_interval,
    )

    try:
        await main_coordinator.async_config_entry_first_refresh()
        await pressure_coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.error(
            "Initial Safetec Water refresh failed for host=%s port=%s: %s",
            host,
            port,
            err,
        )
        return

    _LOGGER.debug(
        "Safetec Water initial data: main=%s pressure=%s",
        main_coordinator.data,
        pressure_coordinator.data,
    )

    device_info = _device_info(host, port, main_coordinator.data)

    descriptions: list[tuple[DataUpdateCoordinator, SafetecWaterSensorDescription, str]] = [
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="volume",
                name="Safetec Water Total Volume",
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            "volume",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="volume_per_hour",
                name="Safetec Water Consumption Per Hour",
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            "volume_per_hour",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="ltv",
                name="Safetec Water Last Tapped Volume",
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            "ltv",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="avo",
                name="Safetec Water Single Consumption",
                native_unit_of_measurement=UnitOfVolume.LITERS,
                device_class=SensorDeviceClass.WATER,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_milliliters_to_liters,
            ),
            "avo",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="flo",
                name="Safetec Water Flow",
                native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            "flo",
        ),
        (
            pressure_coordinator,
            SafetecWaterSensorDescription(
                key="pressure",
                name="Safetec Water Pressure",
                native_unit_of_measurement=UnitOfPressure.BAR,
                device_class=SensorDeviceClass.PRESSURE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_millibar_to_bar,
                force_update=True,
            ),
            "pressure",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="temperature",
                name="Safetec Water Temperature",
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_tenths_to_celsius,
            ),
            "temperature",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="hardness",
                name="Safetec Water Hardness",
                native_unit_of_measurement="°dH",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_uscm_to_hardness,
            ),
            "cnd",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="wifi_state",
                name="Safetec Water WiFi State",
                entity_category=EntityCategory.DIAGNOSTIC,
                value_fn=_wifi_state_name,
            ),
            "wfs",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="battery",
                name="Safetec Water Battery Voltage",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_tenths_to_volts,
            ),
            "battery",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="net",
                name="Safetec Water DC Voltage",
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                device_class=SensorDeviceClass.VOLTAGE,
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=_tenths_to_volts,
            ),
            "net",
        ),
    ]

    entities: list[SensorEntity] = []
    for coordinator, description, data_key in descriptions:
        _LOGGER.debug(
            "Adding Safetec Water sensor: key=%s name=%s coordinator=%s",
            data_key,
            description.name,
            coordinator.name,
        )
        entities.append(
            SafetecWaterSensor(
                coordinator=coordinator,
                description=description,
                data_key=data_key,
                device_info=device_info,
                main_coordinator=main_coordinator,
            )
        )

    async_add_entities(entities)
    _LOGGER.debug("Safetec Water setup complete. Added %d sensors.", len(entities))


class SafetecWaterSensor(CoordinatorEntity[DataUpdateCoordinator], SensorEntity):
    """Safetec Water sensor."""

    entity_description: SafetecWaterSensorDescription

    def __init__(
        self,
        *,
        coordinator: DataUpdateCoordinator,
        description: SafetecWaterSensorDescription,
        data_key: str,
        device_info: DeviceInfo,
        main_coordinator: DataUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._data_key = data_key
        self._attr_device_info = device_info
        self._attr_force_update = description.force_update
        self._main_coordinator = main_coordinator

    @property
    def native_value(self) -> Any:
        value = self.coordinator.data.get(self._data_key)
        if value is None:
            return None
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(value)
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._main_coordinator.data
        valve_status = _valve_status_name(data.get("vlv"))
        return {
            "firmware_version": data.get("firmware"),
            "serial_number": data.get("serial"),
            "conductivity_us_cm": data.get("cnd"),
            "wifi_rssi": data.get("wfr"),
            "wifi_state": _wifi_state_name(data.get("wfs")),
            "ip_address": data.get("wip"),
            "default_gateway": data.get("wgw"),
            "valve_status": valve_status,
            "valve_status_code": data.get("vlv"),
        }


def _extract_value(data: Any, key: str) -> Any:
    if isinstance(data, dict):
        if key in data:
            return data[key]
        if len(data) == 1:
            return next(iter(data.values()))
    return data


def _normalize_api_value(value: Any) -> Any:
    if isinstance(value, str):
        upper_value = value.upper()
        if "ERROR" in upper_value or "MIMA" in upper_value:
            return None
    return value


def _coerce_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _millibar_to_bar(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return round(number / 1000, 3)


def _milliliters_to_liters(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return round(number / 1000, 3)


def _tenths_to_celsius(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return round(number / 10, 1)


def _tenths_to_volts(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return round(number / 10, 2)


def _uscm_to_hardness(value: Any) -> float | None:
    number = _coerce_number(value)
    if number is None:
        return None
    return round(number / 30, 2)


def _wifi_state_name(value: Any) -> str | None:
    if value is None:
        return None
    key = str(value)
    return WIFI_STATE_MAP.get(key, key)


def _valve_status_name(value: Any) -> str | None:
    status_map = {
        10: "Closed",
        11: "Closing",
        20: "Open",
        21: "Opening",
        30: "Undefined",
    }
    number = _coerce_number(value)
    if number is None:
        return None
    return status_map.get(int(number), "Unknown")


def _device_info(host: str, port: int, data: dict[str, Any]) -> DeviceInfo:
    serial = data.get("serial")
    return DeviceInfo(
        identifiers={(DOMAIN, serial or host)},
        name="Safetec Water",
        manufacturer="Safetec",
        serial_number=serial,
        sw_version=data.get("firmware"),
        configuration_url=f"http://{host}:{port}",
    )
