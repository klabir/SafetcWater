"""Safetec Water sensors."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
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
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import aiohttp_client, config_validation as cv
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)
INTEGRATION_VERSION = "1.1"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

MAIN_SCAN_INTERVAL = timedelta(minutes=1)
PRESSURE_SCAN_INTERVAL = timedelta(minutes=1)


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
        temperature = _extract_value(await self._async_get_json("get/cel"), "getCEL")
        battery = _extract_value(await self._async_get_json("get/bat"), "getBAT")
        net = _extract_value(await self._async_get_json("get/net"), "getNET")
        firmware = _extract_value(await self._async_get_json("get/ver"), "getVER")
        serial = _extract_value(await self._async_get_json("get/srn"), "getSRN")

        return {
            "volume": _coerce_number(volume),
            "temperature": _coerce_number(temperature),
            "battery": _coerce_number(battery),
            "net": _coerce_number(net),
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
    """Set up Safetec Water sensors."""

    host = config[CONF_HOST]
    port = config[CONF_PORT]
    _LOGGER.debug(
        "Setting up Safetec Water platform v%s for host=%s port=%s",
        INTEGRATION_VERSION,
        host,
        port,
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = SafetecWaterClient(session, host, port)

    main_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="Safetec Water",
        update_method=client.async_fetch_main,
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
        raise PlatformNotReady from err

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
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="firmware",
                name="Safetec Water Firmware Version",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "firmware",
        ),
        (
            main_coordinator,
            SafetecWaterSensorDescription(
                key="serial",
                name="Safetec Water Serial Number",
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            "serial",
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
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._data_key = data_key
        self._attr_device_info = device_info
        self._attr_force_update = description.force_update

    @property
    def native_value(self) -> Any:
        value = self.coordinator.data.get(self._data_key)
        if value is None:
            return None
        if self.entity_description.value_fn:
            return self.entity_description.value_fn(value)
        return value


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
