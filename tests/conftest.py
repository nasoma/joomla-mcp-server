import httpx
import pytest
from joomlamcp.config import Settings
from joomlamcp.client import JoomlaClient
from joomlamcp.server import create_server


@pytest.fixture(params=["4", "5"])
def factory(request):
    clients = []

    def make(handler, **env):
        settings = Settings.from_env(
            {
                "JOOMLA_BASE_URL": "https://joomla.invalid",
                "BEARER_TOKEN": "dummy-test-token",
                "JOOMLA_READ_RETRIES": "0",
                "JOOMLA_VERSION": request.param,
                **env,
            }
        )
        api = JoomlaClient(settings, httpx.MockTransport(handler))
        clients.append(api)
        return create_server(settings, api), api

    yield make
    # No real sockets are opened by MockTransport.


def resource(resource_id=3, **attributes):
    return {
        "data": {
            "id": str(resource_id),
            "attributes": {"title": "Existing", **attributes},
        }
    }
