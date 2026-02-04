"""Safetec Water sensors."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timedelta
import logging
from typing import Any, Callable

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    UnitOfElectricPotential,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import DEFAULT_PORT, DOMAIN, INTEGRATION_VERSION

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

MAIN_SCAN_INTERVAL = timedelta(seconds=15)
PRESSURE_SCAN_INTERVAL = timedelta(seconds=15)


class VolumeRateTracker:
    """Track volume deltas to calculate usage per hour."""

    def __init__(self) -> None:
        self._samples: deque[tuple[datetime, float]] = deque()

    def add(self, value: float | None) -> None:
        if value is None:
            return
        now = dt_util.utcnow()
        self._samples.append((now, value))
        cutoff = now - timedelta(hours=1)
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()

    def liters_per_hour(self) -> float | None:
        if len(self._samples) < 2:
            return None
        oldest_time, oldest_value = self._samples[0]
        newest_time, newest_value = self._samples[-1]
        elapsed = (newest_time - oldest_time).total_seconds()
        if elapsed <= 0:
            return None
        delta = newest_value - oldest_value
        if delta < 0:
            return None
        return round((delta / elapsed) * 3600, 3)


@dataclass(frozen=True, kw_only=True)
class SafetecWaterSensorDescription(SensorEntityDescription):
    """Describes a Safetec Water sensor."""

    value_fn: Callable[[Any], Any] | None = None
    force_update: bool = False


class SafetecWaterClient:
    """Client for Safetec Water API."""

    def __init__(self, session: aiohttp.ClientSession, host: str, port: int) -> None:
        self._session = session
        self._base_url = f"http://{host}:{port}/trio"

    async def _async_get_json(self, path: str) -> dict[str, Any] | Any:
        url = f"{self._base_url}/{path}"
        try:
            async with async_timeout.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
                    return await response.json()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

    async def _async_fire_and_forget(self, path: str) -> None:
        url = f"{self._base_url}/{path}"
        try:
            async with async_timeout.timeout(10):
                async with self._session.get(url) as response:
                    response.raise_for_status()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise UpdateFailed(f"Error fetching {url}: {err}") from err

    async def async_fetch_main(self) -> dict[str, Any]:
        await self._async_fire_and_forget("set/adm/(2)f")
        volume = _extract_value(await self._async_get_json("get/vol"), "getVOL")
        last_tapped_volume = _extract_value(
            await self._async_get_json("get/ltv"), "getLTV"
        )
        single_consumption = _extract_value(
            await self._async_get_json("get/avo"), "getAVO"
        )
        conductivity = _extract_value(await self._async_get_json("get/cnd"), "getCND")
        flow = _extract_value(await self._async_get_json("get/flo"), "getFLO")
        temperature = _extract_value(await self._async_get_json("get/cel"), "getCEL")
        battery = _extract_value(await self._async_get_json("get/bat"), "getBAT")
        net = _extract_value(await self._async_get_json("get/net"), "getNET")
        wifi_rssi = _extract_value(await self._async_get_json("get/wfr"), "getWFR")
        ip_address = _extract_value(await self._async_get_json("get/wip"), "getWIP")
        gateway = _extract_value(await self._async_get_json("get/wgw"), "getWGW")
        valve_status = _extract_value(await self._async_get_json("get/vlv"), "getVLV")
        firmware = _extract_value(await self._async_get_json("get/ver"), "getVER")
        serial = _extract_value(await self._async_get_json("get/srn"), "getSRN")

        return {
            "volume": _coerce_number(volume),
            "ltv": _coerce_number(last_tapped_volume),
            "avo": _coerce_number(single_consumption),
            "cnd": _coerce_number(conductivity),
            "flo": _coerce_number(flow),
            "temperature": _coerce_number(temperature),
            "battery": _coerce_number(battery),
            "net": _coerce_number(net),
            "wfr": _coerce_number(wifi_rssi),
            "wip": ip_address,
            "wgw": gateway,
            "vlv": _coerce_number(valve_status),
            "firmware": firmware,
            "serial": serial,
        }

    async def async_fetch_pressure(self) -> dict[str, Any]:
        pressure = _extract_value(await self._async_get_json("get/bar"), "getBAR")
        return {"pressure": _coerce_number(pressure)}


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Set up Safetec Water sensors from YAML."""
    await _async_setup_entities(
        hass,
        async_add_entities,
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        raise_not_ready=ConfigEntryNotReady,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Any,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Safetec Water sensors from a config entry."""
    await _async_setup_entities(
        hass,
        async_add_entities,
        host=entry.data[CONF_HOST],
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        raise_not_ready=ConfigEntryNotReady,
    )


async def _async_setup_entities(
    hass: HomeAssistant,
    async_add_entities: AddEntitiesCallback,
    *,
    host: str,
    port: int,
    raise_not_ready: type[Exception],
) -> None:
    _LOGGER.debug(
        "Setting up Safetec Water v%s for host=%s port=%s",
        INTEGRATION_VERSION,
        host,
        port,
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = SafetecWaterClient(session, host, port)

    volume_tracker = VolumeRateTracker()

    async def _update_main() -> dict[str, Any]:
        data = await client.async_fetch_main()
        volume_tracker.add(data.get("volume"))
        data["volume_per_hour"] = volume_tracker.liters_per_hour()
        return data

    main_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Safetec Water",
        update_method=_update_main,
        update_interval=MAIN_SCAN_INTERVAL,
    )
    pressure_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Safetec Water Pressure",
        update_method=client.async_fetch_pressure,
        update_interval=PRESSURE_SCAN_INTERVAL,
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
        raise raise_not_ready from err

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
                native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
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
