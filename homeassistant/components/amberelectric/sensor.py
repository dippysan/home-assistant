"""Support for Amber Electric pricing service."""
import datetime
import logging

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_NAME,
)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_RESOURCE = "https://api-bff.amberelectric.com.au/api/v1.0/Price/GetPriceList"
_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "last_update"
ATTR_SENSOR_ID = "sensor_id"

ATTRIBUTION = "Data provided by Amber Electric"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=60)
COLORS = ["red", "yellow", "green"]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Amber Electric sensor."""
    username, password = config.get(CONF_USERNAME), config.get(CONF_PASSWORD)

    amber_data = AmberCurrentData(username, password)

    try:
        amber_data.update()
    except ValueError as err:
        _LOGGER.error("Received error from Amber Electric: %s", err)
        return

    add_entities([AmberCurrentSensor(amber_data)])


class AmberCurrentSensor(Entity):
    """Implementation of an Amber Electric Current Price sensor."""

    def __init__(self, amber_data):
        """Initialize the sensor."""
        self.amber_data = amber_data

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    @property
    def name(self):
        """Return the name of the sensor."""
        return "AmberElectric"

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self.amber_data._data

    @property
    def state(self):
        """Return the current price."""
        if self.amber_data._data:
            return self.amber_data._data["currentPriceKWH"]

    def update(self):
        """Update current conditions."""
        self.amber_data.update()


class AmberCurrentData:
    """Get data from Amber Electric."""

    def __init__(self, username, password):
        """Initialize the data object."""
        self._username = username
        self._password = password
        self._id_token = None
        self._refresh_token = None
        self._data = None
        self.last_updated = None

    def _build_url(self):
        """Build the URL for the requests."""
        return _RESOURCE

    @property
    def latest_data(self):
        """Return the latest data object."""
        if self._data:
            return self._data
        return None

    def _authorize(self):
        try:
            if self._username is None:
                # Previously couldn't login, so don't try again
                return

            payload = {"username": self._username, "password": self._password}
            result = requests.post(
                "https://api-bff.amberelectric.com.au/api/v1.0/Authentication/SignIn",
                timeout=10,
                data=payload,
                headers={"content-type": "application/json"},
            )
            _LOGGER.debug("Amber Electric Payload: %s", payload)
            _LOGGER.debug("Amber Electric Result %s", result)
            result_json = result.json()
            if result_json["message"] != "Authentication successfully.":
                _LOGGER.debug(
                    "Amber Electric Login Error Message: %s", result_json["message"]
                )
                # Can't login
                self._id_token = None
                self._username = None
                return

            tokens = result_json["data"]
            self._id_token = tokens["idToken"]
            self._refresh_token = tokens["refreshToken"]
            return

        except (KeyError, ValueError) as err:
            template = "Amber Electric Error: type {0}. Arguments: {1!r}. Result: {2}"
            message = template.format(type(err).__name__, err.args, result)
            _LOGGER.error(message)
            self._data = None
            raise

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

        if self._id_token is None:
            self._authorize()

        if self._id_token is None:
            # Can't initialize
            return

        try:
            result = requests.post(
                self._build_url(),
                timeout=10,
                data="",
                headers={
                    "refreshtoken": self._refresh_token,
                    "authorization": self._id_token,
                },
            )
            result_json = result.json()

            _LOGGER.debug("Amber Electric Data Return: %s", result.json())
            if result_json == "Token is not valid":
                # Wipe token so can reauth next time
                self._id_token = None
                return

            self._data = result_json["data"]

            # set lastupdate using self._data[0] as the first element in the
            # array is the latest date in the json
            self.last_updated = dt_util.as_utc(
                datetime.datetime.strptime(
                    str(self._data["currentPricePeriod"]), "%Y-%m-%dT%H:%M:%SZ"
                )
            )
            return

        except (KeyError, ValueError) as err:
            template = "Amber Electric Error: type {0}. Arguments: {1!r}. Result: {2}"
            message = template.format(type(err).__name__, err.args, result)
            _LOGGER.error(message)
            self._data = None
            raise
