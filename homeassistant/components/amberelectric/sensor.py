"""Support for Amber Electric pricing service."""
import datetime
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    CONF_NAME,
    ATTR_ATTRIBUTION,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_RESOURCE = "https://api-bff.amberelectric.com.au/api/v1.0/Price/GetPriceList"
_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"

ATTRIBUTION = "Data provided by Amber Electric"

CONF_ID_TOKEN = "id_token"
CONF_REFRESH_TOKEN = "refresh_token"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)

SENSOR_TYPES = {
    "currentPriceKWH": ["Current Price kWh", ENERGY_KILO_WATT_HOUR],
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_ID_TOKEN): cv.string,
        vol.Optional(CONF_REFRESH_TOKEN): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Amber Electric sensor."""
    id_token, refresh_token = config.get(CONF_ID_TOKEN), config.get(CONF_REFRESH_TOKEN)

    amber_data = AmberCurrentData(id_token, refresh_token)

    try:
        amber_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from Amber Electric: %s", err)
        return

    add_entities(
        [AmberCurrentSensor(amber_data, variable) for variable in SENSOR_TYPES]
    )


class AmberCurrentSensor(Entity):
    """Implementation of an Amber Electric Current Price sensor."""

    def __init__(self, amber_data, condition):
        """Initialize the sensor."""
        self.amber_data = amber_data
        self._condition = condition

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Amber {}".format(SENSOR_TYPES[self._condition][0])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.amber_data._data[self._condition]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_LAST_UPDATE: self.amber_data.last_updated,
            ATTR_SENSOR_ID: self._condition,
        }

        return attr

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return SENSOR_TYPES[self._condition][1]

    def update(self):
        """Update current conditions."""
        self.amber_data.update()


class AmberCurrentData:
    """Get data from Amber Electric."""

    def __init__(self, id_token, refresh_token):
        """Initialize the data object."""
        self._id_token = id_token
        self._refresh_token = refresh_token
        self._data = None
        self.last_updated = None

    def _build_url(self):
        """Build the URL for the requests."""
        _LOGGER.debug("Amber Electric URL: %s", _RESOURCE)
        return _RESOURCE

    @property
    def latest_data(self):
        """Return the latest data object."""
        if self._data:
            return self._data
        return None

    def should_update(self):
        """Determine whether an update should occur.

        Amber Electric provides updated data every 30 minutes. We manually define
        refreshing logic here rather than a throttle to keep updates
        in lock-step with Amber Electric.

        If 35 minutes has passed since the last Amber Electric data update, then
        an update should be done.
        """
        if self.last_updated is None:
            # Never updated before, therefore an update should occur.
            return True

        now = dt_util.utcnow()
        update_due_at = self.last_updated + datetime.timedelta(minutes=35)
        return now > update_due_at

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Amber Electric."""
        if not self.should_update():
            _LOGGER.debug(
                "Amber Electric was updated %s minutes ago, skipping update as"
                " < 35 minutes, Now: %s, LastUpdate: %s",
                (dt_util.utcnow() - self.last_updated),
                dt_util.utcnow(),
                self.last_updated,
            )
            return

        try:
            result = requests.get(
                self._build_url(),
                timeout=10,
                headers={
                    "refreshtoken": self._refresh_token,
                    "authorization": self._id_token,
                },
            ).json()
            self._data = result["data"]
            _LOGGER.debug("Amber Electric URL Result: %s", result)

            # set lastupdate using self._data[0] as the first element in the
            # array is the latest date in the json
            self.last_updated = dt_util.as_utc(
                datetime.datetime.strptime(
                    str(self._data["currentPricePeriod"]), "%Y-%m-%dT%H:%M:%SZ"
                )
            )
            return

        except ValueError as err:
            _LOGGER.error("Check Amber Electric %s", err.args)
            self._data = None
            raise
