"""The API's endpoints, on synthetic public files (no network)."""

from __future__ import annotations

from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path

import pytest
from curbcut_api.data import Store, dir_fetcher
from fastapi.testclient import TestClient


def test_status_ready(client: TestClient) -> None:
    response = client.get("/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["error"] is None
    assert body["files"]["states.json"]["rows"] == 37
    assert body["files"]["dhs2024_state_prevalence.parquet"]["rows"] == 37 * 8
    assert len(body["files"]["poverty.json"]["sha256"]) == 64
    assert body["git_commit"] is None
    assert "about a minute" in body["cold_start"]
    assert body["version"] == "0.1.0"


def test_status_git_commit(make_client: Callable[..., TestClient]) -> None:
    body = make_client({"RENDER_GIT_COMMIT": "abc123"}).get("/status").json()
    assert body["git_commit"] == "abc123"


def test_small_headline_is_dropped(client: TestClient) -> None:
    states = client.get("/states").json()["states"]
    assert states[0]["dhs2024"] is None  # 12 respondents
    assert states[1]["dhs2024"]["n_unweighted"] == 500
    assert client.get("/states/akwa-ibom").json()["state"]["dhs2024"] is None


def test_small_cell_is_suppressed(client: TestClient) -> None:
    # Row 6 of the fixture: Akwa Ibom, seeing_3plus, 5-17, both sexes, 12 respondents.
    params = {"state": "akwa-ibom", "measure": "seeing_3plus", "age_group": "5-17"}
    cell = client.get("/prevalence", params=params).json()["cells"][0]
    assert cell["suppressed"] is True
    for name in ("estimate", "se", "ci_low", "ci_high", "n_unweighted", "n_effective", "df"):
        assert cell[name] is None


def test_prevalence_values_case_insensitive(client: TestClient) -> None:
    body = client.get("/prevalence", params={"measure": "DISABILITY3", "sex": "All"}).json()
    assert body["query"]["measure"] == "disability3"
    assert body["count"] == 37


def test_status_hides_local_path(client: TestClient, data_dir: Path) -> None:
    from curbcut_api.data import store_from_env

    store = store_from_env({"CURBCUT_DATA_DIR": str(data_dir)})
    from curbcut_api.app import create_app

    body = TestClient(create_app({}, store)).get("/status").json()
    assert body["data_source"] == "local directory"
    assert str(data_dir) not in str(body)
    assert data_dir.name not in body["data_source"]


def test_status_error_has_no_internal_detail(
    data_dir: Path, make_client: Callable[..., TestClient]
) -> None:
    (data_dir / "dhs2024_national_zone.parquet").write_bytes(b"not parquet")
    body = make_client().get("/status").json()
    assert body["error"] == "dhs2024_national_zone.parquet failed validation: not readable Parquet"
    assert "tmp" not in body["error"].lower()


def test_states(client: TestClient) -> None:
    body = client.get("/states").json()
    assert body["count"] == 37
    assert body["states"][0]["state"] == "Akwa Ibom"
    assert {"dhs2024", "jonapwd", "population"} <= body["source"].keys()
    assert "not redistributed" in body["source"]["jonapwd"]["terms"]


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("akwa-ibom", "NG-AK"),
        ("Akwa-Ibom", "NG-AK"),
        ("akwa ibom", "NG-AK"),
        ("NG-AK", "NG-AK"),
        ("ng-ak", "NG-AK"),
        ("AK", "NG-AK"),
        ("federal-capital-territory", "NG-FC"),
        ("fake-state-pa", "NG-PA"),
    ],
)
def test_state_lookup(client: TestClient, value: str, code: str) -> None:
    response = client.get(f"/states/{value}")
    assert response.status_code == 200
    body = response.json()
    assert body["state"]["state_code"] == code
    assert body["page"].endswith(f"/states/{body['slug']}.html")


def test_state_unknown(client: TestClient) -> None:
    response = client.get("/states/atlantis")
    assert response.status_code == 404
    message = response.json()["detail"]["message"]
    assert "akwa-ibom" in message and "NG-AK" in message


def test_prevalence_default_is_headline(client: TestClient) -> None:
    body = client.get("/prevalence").json()
    assert body["query"] == {
        "level": "state",
        "measure": "disability3",
        "age_group": "18+",
        "sex": "all",
    }
    assert body["count"] == 37
    assert {c["measure"] for c in body["cells"]} == {"disability3"}
    assert all("precision_flag" in c and "precision_reason" in c for c in body["cells"])
    assert "DHS" in body["source"]["citation"]


def test_prevalence_state_filter(client: TestClient) -> None:
    body = client.get("/prevalence", params={"state": "fake-state-pa", "sex": "female"}).json()
    assert body["query"]["state"] == "NG-PA"
    assert [c["state_code"] for c in body["cells"]] == ["NG-PA"]


def test_prevalence_suppressed_cell_has_no_numbers(client: TestClient) -> None:
    # Row 3 of the fixture: Akwa Ibom, disability3, 5-17, female; its file still holds numbers.
    params = {"state": "akwa-ibom", "age_group": "5-17", "sex": "female"}
    cell = client.get("/prevalence", params=params).json()["cells"][0]
    assert cell["suppressed"] is True
    assert cell["precision_flag"] == "unreliable"
    assert cell["precision_reason"] == "n < 30"
    for name in ("estimate", "se", "ci_low", "ci_high", "n_unweighted", "n_effective", "df"):
        assert cell[name] is None


def test_prevalence_no_data_cell(client: TestClient) -> None:
    params = {"state": "akwa-ibom", "measure": "seeing_3plus", "age_group": "18+", "sex": "female"}
    cell = client.get("/prevalence", params=params).json()["cells"][0]
    assert cell["has_data"] is False
    assert cell["estimate"] is None and cell["se"] is None


def test_prevalence_age_group_plus_unencoded(client: TestClient) -> None:
    # "18+" typed into a URL arrives as "18 ".
    response = client.get("/prevalence?age_group=18+")
    assert response.status_code == 200
    assert response.json()["query"]["age_group"] == "18+"


def test_prevalence_zone_and_national(client: TestClient) -> None:
    zone = client.get("/prevalence", params={"level": "zone", "geography": "zone-two"}).json()
    assert zone["query"]["geography"] == "Zone Two"
    assert [c["geography"] for c in zone["cells"]] == ["Zone Two"]
    zones = client.get("/prevalence", params={"level": "zone"}).json()
    assert zones["count"] == 2
    national = client.get(
        "/prevalence", params={"level": "National", "measure": "hearing_level_1"}
    ).json()
    assert national["cells"][0]["geography"] == "NG"


@pytest.mark.parametrize(
    ("params", "parameter", "allowed"),
    [
        ({"level": "county"}, "level", ["state", "zone", "national"]),
        ({"measure": "hearing_level_1"}, "measure", ["disability3", "seeing_3plus"]),
        ({"age_group": "0-4"}, "age_group", ["18+", "5-17"]),
        ({"sex": "other"}, "sex", ["all", "female"]),
        ({"level": "zone", "geography": "Zone Nine"}, "geography", ["Zone One", "Zone Two"]),
    ],
)
def test_prevalence_invalid_values_list_allowed(
    client: TestClient, params: dict[str, str], parameter: str, allowed: list[str]
) -> None:
    response = client.get("/prevalence", params=params)
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["parameter"] == parameter
    assert detail["allowed"] == allowed


def test_prevalence_parameter_mismatch(client: TestClient) -> None:
    assert client.get("/prevalence", params={"geography": "Zone One"}).status_code == 422
    response = client.get("/prevalence", params={"level": "zone", "state": "akwa-ibom"})
    assert response.status_code == 422
    assert client.get("/prevalence", params={"state": "atlantis"}).status_code == 404


def test_prevalence_combination_absent(client: TestClient) -> None:
    params = {"level": "national", "measure": "hearing_level_1", "sex": "female"}
    response = client.get("/prevalence", params=params)
    assert response.status_code == 404
    assert response.json()["detail"]["query"]["sex"] == "female"


def test_compare_sorted(client: TestClient) -> None:
    body = client.get("/compare").json()
    assert [r["figure_id"] for r in body["rows"]] == ["a", "b"]
    assert body["rows"][0]["source_url"] == "https://example.org/"


def test_poverty(client: TestClient) -> None:
    body = client.get("/poverty").json()
    assert body["note"] == "Invented note."
    assert body["estimates"]["primary"]["estimate"] == 0.1
    assert "derived" not in body
    assert "adjusted association" in body["wording"]
    assert "MPI" in body["source"]["citation"]


def test_cors_allows_any_origin_for_get(client: TestClient) -> None:
    response = client.get("/states", headers={"Origin": "https://example.org"})
    assert response.headers["access-control-allow-origin"] == "*"
    assert "set-cookie" not in response.headers


class _Outline(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.links: list[str] = []
        self.lang: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        if tag == "html":
            self.lang = dict(attrs).get("lang")
        if tag == "a":
            self.links.append(dict(attrs).get("href") or "")


def test_home_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    page = _Outline()
    page.feed(response.text)
    assert page.lang == "en"
    assert page.tags.count("h1") == 1
    assert page.tags.count("main") == 1
    assert "title" in page.tags
    for href in ("/docs", "/status", "/states", "/prevalence", "/compare", "/poverty"):
        assert href in page.links
    assert "https://batestguy.github.io/curb-cut/" in page.links
    assert "about a minute" in response.text
    assert "not redistributed" in response.text


def test_docs_and_openapi(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    spec = client.get("/openapi.json").json()
    for path in ("/status", "/states", "/states/{state}", "/prevalence", "/compare", "/poverty"):
        assert set(spec["paths"][path]) == {"get"}
    description = " ".join(spec["info"]["description"].split())
    for phrase in ("never depends on", "No microdata", "not redistributed", "about a minute"):
        assert phrase in description


def test_only_get(client: TestClient) -> None:
    assert client.post("/states").status_code == 405


# Loading failures: 503 with a reason, a backoff, then recovery.


class FlakyFetch:
    def __init__(self, directory: Path) -> None:
        self.inner = dir_fetcher(directory)
        self.fail = True
        self.calls = 0

    def __call__(self, name: str) -> bytes:
        self.calls += 1
        if self.fail:
            raise OSError("network unreachable")
        return self.inner(name)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_download_failure_then_recovery(
    data_dir: Path, make_client: Callable[..., TestClient]
) -> None:
    fetch, clock = FlakyFetch(data_dir), Clock()
    store = Store(fetch, "https://example.invalid/data/", clock=clock)
    client = make_client(store=store)

    status = client.get("/status")
    assert status.status_code == 503
    body = status.json()
    assert body["ready"] is False
    # The public message names the file; the exception text goes only to the log.
    assert body["error"] == "could not fetch dhs2024_state_prevalence.parquet"
    assert body["next_retry_in_seconds"] == 30
    response = client.get("/states")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"
    assert "not loaded" in response.json()["detail"]["message"]
    assert fetch.calls == 1  # no retry inside the backoff

    fetch.fail = False
    clock.now += 10
    assert client.get("/prevalence").status_code == 503
    assert fetch.calls == 1
    clock.now += 21
    assert client.get("/states").status_code == 200
    assert store.attempts == 2
    status = client.get("/status")
    assert status.status_code == 200
    assert status.json()["next_retry_in_seconds"] is None


def test_concurrent_request_does_not_wait_for_a_load(data_dir: Path) -> None:
    import threading

    started, release = threading.Event(), threading.Event()
    inner = dir_fetcher(data_dir)

    def slow_fetch(name: str) -> bytes:
        started.set()
        release.wait(10)
        return inner(name)

    store = Store(slow_fetch, "x")
    loader = threading.Thread(target=store.ensure)
    loader.start()
    assert started.wait(10)
    # Another request while the load runs gets the current state at once (None -> 503).
    assert store.ensure() is None
    assert store.attempts == 1
    release.set()
    loader.join(10)
    assert store.ensure() is not None
    assert store.attempts == 1


def test_backoff_doubles_and_caps(data_dir: Path) -> None:
    fetch, clock = FlakyFetch(data_dir), Clock()
    store = Store(fetch, "x", clock=clock)
    waits = []
    for _ in range(7):
        store.ensure()
        wait = store.retry_in()
        assert wait is not None
        waits.append(wait)
        clock.now += wait
    assert waits == [30, 60, 120, 240, 480, 600, 600]


def test_bad_file_reported_by_status(
    data_dir: Path, make_client: Callable[..., TestClient]
) -> None:
    (data_dir / "states.json").write_text("[]", encoding="utf-8")
    body = make_client().get("/status").json()
    assert body["ready"] is False
    assert "37 states" in body["error"]


def test_startup_loads_once(make_client: Callable[..., TestClient], data_dir: Path) -> None:
    store = Store(dir_fetcher(data_dir), "x")
    with make_client(store=store) as client:  # runs the lifespan
        assert store.data is not None
        assert client.get("/states").status_code == 200
    assert store.attempts == 1


def test_startup_survives_failure(make_client: Callable[..., TestClient], data_dir: Path) -> None:
    store = Store(FlakyFetch(data_dir), "x")
    with make_client(store=store) as client:
        assert client.get("/status").status_code == 503
    assert store.error is not None and "could not fetch" in store.error
