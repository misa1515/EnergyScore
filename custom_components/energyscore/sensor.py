"""Sensor platform for integration_blueprint."""
import datetime
from datetime import timedelta
from typing import Callable, Any
import logging

import numpy as np
import voluptuous as vol

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
    PLATFORM_SCHEMA,
)
from homeassistant.const import CONF_NAME, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    Optional,
    DiscoveryInfoType,
)
from homeassistant.util import dt

from .const import CONF_ENERGY_ENTITY, CONF_PRICE_ENTITY

_LOGGER: logging.Logger = logging.getLogger(__package__)

# Time between updating data TODO: Set to be triggered by a new data point (every whole hour?)
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENERGY_ENTITY): cv.entity_id,
        vol.Required(CONF_PRICE_ENTITY): cv.entity_id,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    """Set up the sensors from YAML config"""
    # sensors = [EnergyScore(sensor) for sensor in config[CONF_NAME]]
    # async_add_entities(sensors)
    async_add_entities([EnergyScore(hass, config)], update_before_add=False)


class EnergyScore(SensorEntity):
    """EnergyScore Sensor class."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass, config):
        self._current_price = None  # TODO: Not needed?
        self._current_energy = None  # TODO: Not needed? or maybe define it with :?
        self._energy_total = {}
        self._energy = {}
        self._energy_array = np.array(None)
        self._energy_entity = config[CONF_ENERGY_ENTITY]
        self._last_updated = None
        self._name = config[CONF_NAME]
        self._norm_energy = np.array(None)
        self._norm_prices = np.array(None)
        self._price_array = np.array(None)
        self._price_entity = config[CONF_PRICE_ENTITY]
        self._prices = {}
        self._quality = 0
        self._state = None
        self._yesterday_energy = None
        self.attr = {
            "energy entity": self._energy_entity,
            "price entity": self._price_entity,
            "quality": self._quality,
        }
        self.entity_id = f"sensor.{self._name}".replace(" ", "_").lower()
        try:
            self._attr_unique_id = config[CONF_UNIQUE_ID]
        except:
            pass

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> Any:
        return self._state

    @property
    def extra_state_attributes(self):
        return self.attr

    def process_new_data(self):
        """Processes the update data"""
        now = dt.now()
        self._quality = len(self._prices) / (int(now.hour) + 1)

        if self._last_updated != now.date():
            self._quality = 0
            self._prices = {}
            self._energy = {}
            if self._last_updated == now.date() - datetime.timedelta(1):
                self._yesterday_energy = max(self._energy_total.values())
            self._energy_total = {}

        self._energy_total[int(now.hour)] = self._current_energy
        _LOGGER.debug("%s - Total energy update: %s", self._name, self._energy_total)

        if (int(now.hour) - int(1)) in self._energy_total:
            self._energy[now.hour] = round(
                (self._current_energy - self._energy_total[int(now.hour) - 1]),
                2,  # Should maybe check highest key instead (what if hours w/o data)?
            )
        elif self._yesterday_energy is not None:
            self._energy[now.hour] = round(
                self._current_energy - self._yesterday_energy, 2
            )
        else:
            _LOGGER.debug(
                "%s - Not enough data to update the EnergyScore yet", self._name
            )
            return

        self._prices[int(now.hour)] = self._current_price
        _LOGGER.debug("%s - Energy: %s", self._name, self._energy)
        _LOGGER.debug("%s - Price: %s", self._name, self._prices)

        self._quality = len(self._prices) / (int(now.hour) + 1)

        self._price_array = np.array(list(self._prices.values()))
        if len(self._prices) > 1:
            self._norm_prices = (self._price_array.max() - self._price_array) / (
                self._price_array.max() - self._price_array.min()
            )
        elif len(self._prices) == 1:
            self._norm_prices = 1
        _LOGGER.debug("%s - Normalised prices: %s", self._name, self._norm_prices)

        self._energy_array = np.array(list(self._energy.values()))
        if self._energy_array.sum() == 0:
            self._norm_energy = list(self._energy.values())
        else:
            self._norm_energy = self._energy_array / self._energy_array.sum()
        _LOGGER.debug("%s - Normalised energy: %s", self._name, self._norm_energy)

        return round(np.dot(self._norm_prices, self._norm_energy), 1)

    async def async_update(self):
        """Updates the sensor"""
        try:
            self._current_price = self.hass.states.get(self._price_entity).state
            self._current_energy = self.hass.states.get(self._energy_entity).state

            if (
                self._current_price == "unavailable"
                or self._current_energy == "unavailable"
            ):
                _LOGGER.exception("%s - Price and/or energy data is unavailable", self._name)
                return
            else:
                self._current_price = round(float(self._current_price), 2)
                self._current_energy = round(float(self._current_energy), 2)

        except:
            _LOGGER.exception("%s - Could not fetch price and energy data", self._name)
        else:
            try:
                self._state = self.process_new_data()
            except:
                _LOGGER.exception(
                    "%s - Could not process the updated data and produce the new EnergyScore", self._name
                )
            else:
                self._last_updated = dt.now().date()


# TODO: What if not used energy? i.e. same energy in all hours.. 100% score?
