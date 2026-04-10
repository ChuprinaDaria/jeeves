from unittest.mock import patch, MagicMock

import pytest
import requests

from Jeeves.concierge_platform import gumroad_client
from Jeeves.concierge_platform.gumroad_client import GumroadResult, verify_license


@pytest.fixture(autouse=True)
def _product_id(settings):
    settings.GUMROAD_PRODUCT_ID = "test_product_id"


def _mock_response(status_code=200, json_data=None):
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data or {}
    m.text = str(json_data)
    return m


class TestVerifyLicense:
    def test_valid_response(self):
        resp = _mock_response(200, {
            "success": True,
            "uses": 1,
            "purchase": {
                "email": "buyer@example.com",
                "product_id": "abc123",
            },
        })
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("test-key")
        assert result.outcome == "valid"
        assert result.data["uses"] == 1
        assert result.data["purchase"]["email"] == "buyer@example.com"
        assert result.error == ""

    def test_invalid_response(self):
        resp = _mock_response(200, {"success": False, "message": "Not found"})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("bad-key")
        assert result.outcome == "invalid"
        assert "Not found" in result.error

    def test_timeout(self):
        with patch.object(
            gumroad_client.requests, "post",
            side_effect=requests.Timeout("timed out"),
        ):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "timeout" in result.error.lower()

    def test_connection_error(self):
        with patch.object(
            gumroad_client.requests, "post",
            side_effect=requests.ConnectionError("dns"),
        ):
            result = verify_license("any-key")
        assert result.outcome == "network_error"

    def test_5xx_response(self):
        resp = _mock_response(503, {})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "503" in result.error

    def test_unexpected_4xx_response(self):
        resp = _mock_response(400, {})
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"
        assert "400" in result.error

    def test_malformed_json(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.side_effect = ValueError("bad json")
        resp.text = "not json"
        with patch.object(gumroad_client.requests, "post", return_value=resp):
            result = verify_license("any-key")
        assert result.outcome == "network_error"

    def test_sends_product_id_and_key(self):
        resp = _mock_response(200, {"success": True, "uses": 1, "purchase": {}})
        with patch.object(
            gumroad_client.requests, "post", return_value=resp,
        ) as mock_post:
            verify_license("the-key")
        args, kwargs = mock_post.call_args
        assert args[0] == gumroad_client.GUMROAD_VERIFY_URL
        sent = kwargs.get("data") or kwargs.get("json") or {}
        assert sent.get("product_id") == "test_product_id"
        assert sent.get("license_key") == "the-key"
