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
from homeassistant.const import (
    CONF_NAME,
    CONF_UNIQUE_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import (
    ConfigType,
    Optional,
    DiscoveryInfoType,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt

from .const import CONF_ENERGY_ENTITY, CONF_PRICE_ENTITY, ICON, QUALITY

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


class EnergyScore(SensorEntity, RestoreEntity):
    """EnergyScore Sensor class."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(self, hass, config):
        self._energies = {}
        self._energy = None  # TODO: Not needed? or maybe define it with :?
        self._energy_total = {}
        self._energy_array = np.array(None)
        self._energy_entity = config[CONF_ENERGY_ENTITY]
        self._last_updated = None
        self._name = config[CONF_NAME]
        self._norm_energy = np.array(None)
        self._norm_prices = np.array(None)
        self._price = None  # TODO: Not needed?
        self._price_array = np.array(None)
        self._price_entity = config[CONF_PRICE_ENTITY]
        self._prices = {}
        self._quality = 0
        self._state = 100
        self._yesterday_energy = None
        self.attr = {
            CONF_ENERGY_ENTITY: self._energy_entity,
            CONF_PRICE_ENTITY: self._price_entity,
            QUALITY: self._quality,
        }
        self._attr_icon: str = ICON
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

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        _LOGGER.debug("Trying to restore: %s", self._name)
        await super().async_added_to_hass()
        if (
            last_state := await self.async_get_last_state()
        ) and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug("Restored %s", self._name)
            # BY THE WAY -- The price and energy arrays should also be stored in the attr to be restored..
            self._state = last_state.state
            self.attr[QUALITY] = last_state.attributes[QUALITY]
        else:
            _LOGGER.debug("Was not able to restore %s", self._name)

    def process_new_data(self):
        """Processes the update data"""
        now = dt.now()

        if self._last_updated != now.date():
            self._quality = 0  # Need to update?
            self._prices = {}
            self._energies = {}
            if self._last_updated == now.date() - datetime.timedelta(1):
                self._yesterday_energy = max(self._energy_total.values())
            self._energy_total = {}

        self._energy_total[int(now.hour)] = self._energy.state
        _LOGGER.debug("%s - Total energy: %s", self._name, self._energy_total)

        if (int(now.hour) - int(1)) in self._energy_total:
            self._energies[now.hour] = round(
                (self._energy.state - self._energy_total[int(now.hour) - 1]),
                2,  # Should maybe check highest key instead (what if hours w/o data)?
            )
        elif self._yesterday_energy is not None:
            self._energies[now.hour] = round(
                self._energy.state - self._yesterday_energy, 2
            )
        else:
            _LOGGER.debug(
                "%s - Not enough data to update the EnergyScore yet", self._name
            )
            return 100

        self._prices[int(now.hour)] = self._price.state
        _LOGGER.debug("%s - Energy: %s", self._name, self._energies)
        _LOGGER.debug("%s - Price: %s", self._name, self._prices)

        self._quality = round(len(self._prices) / (int(now.hour) + 1), 2)
        self.attr[QUALITY] = self._quality
        _LOGGER.debug("%s - Quality: %s", self._name, self._quality)

        self._price_array = np.array(list(self._prices.values()))
        if len(self._prices) > 1:
            self._norm_prices = (self._price_array.max() - self._price_array) / (
                self._price_array.max() - self._price_array.min()
            )
        elif len(self._prices) == 1:
            self._norm_prices = self._price_array / self._price_array.sum()
        _LOGGER.debug("%s - Normalised prices: %s", self._name, self._norm_prices)

        self._energy_array = np.array(list(self._energies.values()))
        if self._energy_array.sum() == 0:
            return 100
        else:
            self._norm_energy = self._energy_array / self._energy_array.sum()
        _LOGGER.debug("%s - Normalised energy: %s", self._name, self._norm_energy)

        self._score = np.dot(self._norm_prices, self._norm_energy)

        _LOGGER.debug("%s - Score: %s", self._name, self._score)

        return int(self._score * 100)

    async def async_update(self):
        """Updates the sensor"""
        try:
            self._price = self.hass.states.get(self._price_entity)
            self._energy = self.hass.states.get(self._energy_entity)

            if self._price.state in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ) or self._energy.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                _LOGGER.info("%s - Price and/or energy data is unavailable", self._name)
                return
            else:
                self._price.state = round(float(self._price.state), 2)
                self._energy.state = round(float(self._energy.state), 2)

        except:
            _LOGGER.exception("%s - Could not fetch price and energy data", self._name)
        else:
            try:
                self._state = self.process_new_data()
            except:
                _LOGGER.exception(
                    "%s - Could not process the updated data and produce the new EnergyScore",
                    self._name,
                )
            else:
                self._last_updated = dt.now().date()
