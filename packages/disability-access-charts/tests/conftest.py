import urllib.request

import pytest


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never make network calls: any urlopen raises."""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("tests must not make network calls")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
