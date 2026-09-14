import pytest


@pytest.mark.parametrize("path", [
    "/api/dashboard/metrics", "/api/chats", "/api/items", "/api/escalations",
    "/api/search?q=hello", "/api/agent-runs", "/api/ingest/jobs",
])
def test_read_routes_are_registered_and_require_auth(client, path):
    assert client.get(path).status_code == 401
