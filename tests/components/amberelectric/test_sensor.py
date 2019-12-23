"""The tests for the Amber Electric sensor platform."""
import json
import re
import unittest
from unittest.mock import patch
from urllib.parse import urlparse

import requests

from homeassistant.components import sensor
from homeassistant.components.amberelectric.sensor import AmberCurrentData
from homeassistant.setup import setup_component
from tests.common import assert_setup_component, get_test_home_assistant, load_fixture
from homeassistant.const import STATE_UNKNOWN

VALID_CONFIG = {
    "platform": "amberelectric",
    "username": "user",
    "password": "pass",
}

VALID_CONFIG_INVALID_USER = {
    "platform": "amberelectric",
    "username": "invaliduser",
    "password": "pass",
}

VALID_CONFIG_INVALID_TOKEN = {
    "platform": "amberelectric",
    "username": "invalidtoken",
    "password": "pass",
}


class MockResponse:
    """Class to represent a mocked response."""

    def __init__(self, json_data, status_code):
        """Initialize the mock response class."""
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Return the json of the response."""
        return self.json_data

    @property
    def content(self):
        """Return the content of the response."""
        return self.json()

    def raise_for_status(self):
        """Raise an HTTPError if status is not 200."""
        if self.status_code != 200:
            raise requests.HTTPError(self.status_code)


times_invalid_signin_called = 0


def mocked_requests(*args, **kwargs):
    """Mock requests.get invocations."""
    global times_invalid_signin_called

    url = urlparse(args[0])

    # Happy path
    if (
        re.match(r".*?SignIn", url.path)
        and kwargs["json"]["username"] == "user"
        and kwargs["json"]["password"] == "pass"
    ):
        return MockResponse(json.loads(load_fixture("amberelectric_signin.json")), 200)
    if (
        re.match(r".*?GetPriceList", url.path)
        and kwargs["headers"]["refreshtoken"] == "refresh"
        and kwargs["headers"]["authorization"] == "token"
    ):
        return MockResponse(json.loads(load_fixture("amberelectric_sensor.json")), 200)

    # Login with invalid user/pass
    if (
        re.match(r".*?SignIn", url.path)
        and kwargs["json"]["username"] == "invaliduser"
        and kwargs["json"]["password"] == "pass"
    ):
        return MockResponse(
            json.loads(load_fixture("amberelectric_invalid_username.json")), 200
        )

    # Simulate token invalid
    if (
        re.match(r".*?SignIn", url.path)
        and kwargs["json"]["username"] == "invalidtoken"
        and kwargs["json"]["password"] == "pass"
    ):
        # Initially returns refresh_invalid_token to force a "Token is not valid" message, then normal data from then on
        if times_invalid_signin_called == 0:
            times_invalid_signin_called += 1
            return MockResponse(
                json.loads(load_fixture("amberelectric_invalid_token.json")), 200
            )
        else:
            return MockResponse(
                json.loads(load_fixture("amberelectric_signin.json")), 200
            )

    if (
        re.match(r".*?GetPriceList", url.path)
        and kwargs["headers"]["refreshtoken"] == "refresh_invalid_token"
        and kwargs["headers"]["authorization"] == "invalid_token"
    ):
        return MockResponse("Token is not valid", 400)

    raise NotImplementedError("Unknown route {} with {}".format(url.path, kwargs))


class TestAmberCurrentSensor(unittest.TestCase):
    """Test the Amber Electric sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("requests.post", side_effect=mocked_requests)
    def test_setup(self, mock_post):
        """Test the setup with custom settings."""
        with assert_setup_component(1, sensor.DOMAIN):
            assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})

        state = self.hass.states.get("sensor.amberelectric")
        assert state is not None
        assert state.state == "27.0"

    @patch("requests.post", side_effect=mocked_requests)
    def test_setup_invalid_user(self, mock_post):
        """Test the setup with custom settings."""
        setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG_INVALID_USER})

        state = self.hass.states.get("sensor.amberelectric")
        assert state is not None
        assert state.state == STATE_UNKNOWN

    @patch("requests.post", side_effect=mocked_requests)
    def test_sensor_attributes(self, mock_post):
        """Test retrieval of sensor values."""
        assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})

        state = self.hass.states.get("sensor.amberelectric")
        assert state is not None
        assert state.state == "27.0"

        print(state.attributes)
        assert dict(state.attributes) == {
            "friendly_name": "AmberElectric",
            "currentPriceKWH": 27.0,
            "currentRenewableInGrid": 10.0,
            "currentPriceColor": "red",
            "currentPricePeriod": "2019-11-27T19:30:00Z",
            "forecastPrices": [
                {
                    "period": "2019-11-28T01:30:00Z",
                    "priceKWH": 25.0,
                    "renewableInGrid": 10.00,
                    "color": "yellow",
                },
                {
                    "period": "2019-11-28T02:00:00Z",
                    "priceKWH": 26.0,
                    "renewableInGrid": 8.00,
                    "color": "red",
                },
                {
                    "period": "2019-11-28T02:30:00Z",
                    "priceKWH": 24.0,
                    "renewableInGrid": 5.00,
                    "color": "yellow",
                },
                {
                    "period": "2019-11-28T03:00:00Z",
                    "priceKWH": 22.0,
                    "renewableInGrid": 5.00,
                    "color": "green",
                },
                {
                    "period": "2019-11-28T03:30:00Z",
                    "priceKWH": 22.0,
                    "renewableInGrid": 5.00,
                    "color": "green",
                },
            ],
            "previousPrices": [
                {
                    "period": "2019-11-26T21:30:00Z",
                    "priceKWH": 26.0,
                    "renewableInGrid": 7.00,
                    "color": "red",
                },
                {
                    "period": "2019-11-26T22:00:00Z",
                    "priceKWH": 24.0,
                    "renewableInGrid": 8.00,
                    "color": "yellow",
                },
                {
                    "period": "2019-11-26T22:30:00Z",
                    "priceKWH": 24.0,
                    "renewableInGrid": 8.00,
                    "color": "yellow",
                },
            ],
        }


class TestAmberCurrentData(unittest.TestCase):
    """Test the Amber data container."""

    def test_should_update_initial(self):
        """Test that the first update always occurs."""
        amber_data = AmberCurrentData("user", "pass")
        assert amber_data.should_update() is True

    @patch("requests.post", side_effect=mocked_requests)
    def test_invalid_token(self, mock_post):
        """Test the setup with custom settings."""
        amber_data = AmberCurrentData("invalidtoken", "pass")

        update_without_throttle = amber_data.update.__wrapped__
        update_without_throttle(amber_data)
        assert amber_data.latest_data is None

        update_without_throttle(amber_data)
        assert amber_data.latest_data["currentPriceKWH"] == 27.0
