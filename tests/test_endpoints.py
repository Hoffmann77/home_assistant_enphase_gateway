"""Tests module"""

import json
import logging
from pathlib import Path

import respx
import pytest
from httpx import Response

from custom_components.enphase_gateway.gateway_reader import GatewayReader


LOGGER = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent.joinpath("fixtures")


def load_fixture(name, path):
    """Load fixure."""
    fp = FIXTURES_DIR.joinpath(name, path.replace("/", "_"))
    with fp.open() as file:
        return file.read()


async def gen_response(name, path):
    """Generate response from fixture name and endpoint path."""
    fname = path.replace("/", "_")
    fname_log = fname + "_log.json"

    fp = FIXTURES_DIR.joinpath(name, fname)
    fp_log = FIXTURES_DIR.joinpath(name, fname_log)

    # get the status code from the log.json file
    if fp_log.is_file():
        with fp_log.open() as json_file:
            log_data = json.load(json_file)
        status_code = log_data.get("code", 200)
        headers = log_data.get("headers", None)
    else:
        status_code = 200
        headers = None

    with fp.open() as file:
        response_data = file.read()

        if fp.stem == ".json":
            return Response(
                status_code=status_code,
                headers=headers,
                json=json.loads(response_data),
            )
        else:
            return Response(
                status_code=status_code,
                headers=headers,
                text=response_data,
            )


@respx.mock
async def get_gateway(fixture_name):
    """Get the gateway."""
    # mock the info endpoint
    respx.get("/info").mock(
        return_value=Response(200, text=load_fixture(fixture_name, "info"))
    )

    gateway_reader = GatewayReader("127.0.0.1")
    await gateway_reader.prepare()
    await gateway_reader.authenticate("username", "password")
    return gateway_reader.gateway

    for endpoint in gateway_reader.gateway.required_endpoints:
        return_value = await gen_response(fixture_name, endpoint.path)
        respx.get(f"/{endpoint.path}").mock(return_value=return_value)

    await gateway_reader.update()
    await gateway_reader.update()
    return gateway_reader.gateway


@pytest.mark.asyncio
@respx.mock
async def test_with_3_7_0_firmware():
    """Test with 3.7.0 firmware."""
    # Config --->
    fixture_name = "3.7.0"
    gateway_class = "EnvoyLegacy"

    gateway = await get_gateway(fixture_name)

    assert gateway.__class__.__name__ == gateway_class

    assert gateway.production == 6.63 * 1000
    assert gateway.daily_production == 53.6 * 1000
    assert gateway.seven_days_production == 405 * 1000
    assert gateway.lifetime_production == 133 * 1000000


@pytest.mark.asyncio
@respx.mock
async def test_with_3_9_36_firmware():
    """Test with 3.9.36 firmware."""
    # Config --->
    fixture_name = "3.9.36"
    gateway_class = "Envoy"

    gateway = await get_gateway(fixture_name)

    assert gateway.__class__.__name__ == gateway_class

    assert gateway.production == 1271
    assert gateway.daily_production == 1460
    assert gateway.seven_days_production == 130349
    assert gateway.lifetime_production == 6012540
    assert gateway.inverters_production[121547060495] == {
        "serialNumber": "121547060495",
        "lastReportDate": 1618083959,
        "lastReportWatts": 135,
        "maxReportWatts": 228
    }
