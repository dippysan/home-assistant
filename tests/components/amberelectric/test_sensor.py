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


VALID_CONFIG = {
    "platform": "amberelectric",
    "id_token": "id",
    "refresh_token": "refresh",
}


def mocked_requests(*args, **kwargs):
    """Mock requests.get invocations."""

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

    url = urlparse(args[0])
    if re.match(r".*?GetPriceList", url.path):
        return MockResponse(json.loads(load_fixture("amberelectric_sensor.json")), 200)

    raise NotImplementedError("Unknown route {}".format(url.path))


class TestAmberCurrentSensor(unittest.TestCase):
    """Test the Amber Electric sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch("requests.get", side_effect=mocked_requests)
    def test_setup(self, mock_get):
        """Test the setup with custom settings."""
        with assert_setup_component(1, sensor.DOMAIN):
            assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})

        fake_entities = [
            "amber_current_price_kwh",
        ]

        for entity_id in fake_entities:
            state = self.hass.states.get("sensor.{}".format(entity_id))
            assert state is not None

    @patch("requests.get", side_effect=mocked_requests)
    def test_sensor_values(self, mock_get):
        """Test retrieval of sensor values."""
        assert setup_component(self.hass, sensor.DOMAIN, {"sensor": VALID_CONFIG})

        currentPrice = self.hass.states.get("sensor.amber_current_price_kwh").state
        assert "27.0" == currentPrice


class TestAmberCurrentData(unittest.TestCase):
    """Test the Amber data container."""

    def test_should_update_initial(self):
        """Test that the first update always occurs."""
        amber_data = AmberCurrentData("id", "refresh")
        assert amber_data.should_update() is True
