"""Rate limiting per client address, with and without trusting X-Forwarded-For."""

from __future__ import annotations

from collections.abc import Callable

from curbcut_api.app import client_key
from fastapi.testclient import TestClient
from starlette.requests import Request

LIMIT = {"CURBCUT_RATE_LIMIT": "3/minute"}


def _request(xff: str | None, peer: str = "10.0.0.1") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def test_429_with_retry_after(make_client: Callable[..., TestClient]) -> None:
    client = make_client(LIMIT)
    # One budget across routes, not one per route.
    for path in ("/states", "/compare", "/prevalence"):
        assert client.get(path).status_code == 200
    response = client.get("/poverty")
    assert response.status_code == 429
    wait = int(response.headers["retry-after"])
    assert 1 <= wait <= 60
    assert response.json()["detail"]["retry_after_seconds"] == wait
    assert "3 per 1 minute" in response.json()["detail"]["message"]


def test_status_is_not_limited(make_client: Callable[..., TestClient]) -> None:
    client = make_client(LIMIT)
    for _ in range(3):
        client.get("/states")
    assert client.get("/states").status_code == 429
    for _ in range(5):
        assert client.get("/status").status_code == 200


def test_untrusted_header_is_ignored(make_client: Callable[..., TestClient]) -> None:
    # Without CURBCUT_TRUST_PROXY, rotating X-Forwarded-For does not buy more requests.
    client = make_client(LIMIT)
    codes = [
        client.get("/states", headers={"X-Forwarded-For": f"198.51.100.{i}"}).status_code
        for i in range(4)
    ]
    assert codes == [200, 200, 200, 429]


def test_trusted_proxy_keys_on_the_proxy_added_entry(
    make_client: Callable[..., TestClient],
) -> None:
    client = make_client(LIMIT | {"CURBCUT_TRUST_PROXY": "1"})
    # Client 203.0.113.7 behind two proxy hops, spoofing a different first entry each time.
    codes = [
        client.get(
            "/states", headers={"X-Forwarded-For": f"192.0.2.{i}, 203.0.113.7, 104.16.0.1"}
        ).status_code
        for i in range(4)
    ]
    assert codes == [200, 200, 200, 429]
    # A different real client has its own budget.
    other = client.get("/states", headers={"X-Forwarded-For": "203.0.113.8, 104.16.0.1"})
    assert other.status_code == 200


def test_status_counts_short_chains(make_client: Callable[..., TestClient]) -> None:
    client = make_client({"CURBCUT_TRUST_PROXY": "1"})
    assert client.get("/status").json()["proxy_chain_shorter_than_hops_seen"] == 0
    client.get("/states", headers={"X-Forwarded-For": "203.0.113.7"})
    client.get("/states", headers={"X-Forwarded-For": "203.0.113.7, 104.16.0.1"})
    body = client.get("/status").json()
    assert body["proxy_chain_shorter_than_hops_seen"] == 1
    assert body["proxy_hops"] == 2
    assert "203.0.113.7" not in str(body)
    untrusted = make_client().get("/status").json()
    assert untrusted["proxy_chain_shorter_than_hops_seen"] is None


def test_client_key_rules() -> None:
    untrusted = client_key(trust_proxy=False, hops=2)
    assert untrusted(_request("1.1.1.1, 2.2.2.2")) == "10.0.0.1"
    trusted = client_key(trust_proxy=True, hops=2)
    assert trusted(_request("9.9.9.9, 1.1.1.1, 2.2.2.2")) == "1.1.1.1"
    assert trusted(_request("1.1.1.1, 2.2.2.2")) == "1.1.1.1"
    assert trusted(_request("1.1.1.1")) == "1.1.1.1"  # fewer entries than hops
    # A short chain falls back to the rightmost entry, never the client-controlled leftmost.
    short: list[int] = []
    three = client_key(trust_proxy=True, hops=3, on_short=lambda: short.append(1))
    assert three(_request("1.1.1.1, 2.2.2.2")) == "2.2.2.2"
    assert three(_request("9.9.9.9, 1.1.1.1, 2.2.2.2")) == "9.9.9.9"
    assert short == [1]
    assert trusted(_request(None)) == "10.0.0.1"
    assert trusted(_request(" , ")) == "10.0.0.1"
    assert client_key(trust_proxy=True, hops=1)(_request("9.9.9.9, 1.1.1.1")) == "1.1.1.1"
    no_peer = Request({"type": "http", "headers": [], "client": None})
    assert untrusted(no_peer) == "unknown"
