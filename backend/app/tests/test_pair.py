"""API tests for POST /api/bill/pair (dual-account side-by-side trial).

Sets DATA_DIR to a throwaway dir before any app import so the seeded
sqlite DB lands outside the repo. Must not import app.config/app.db first.
"""

import json
import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="ladderbill_pair_test_")

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def pair_body(**over):
    body = {
        "left": {"account_id": 1, "kwh": 120, "peak": False},
        "right": {"account_id": 2, "kwh": 400, "peak": True},
    }
    for key, val in over.items():
        if key in ("left", "right"):
            body[key].update(val)
        else:
            body[key] = val
    return body


def history_count(client):
    return len(client.get("/api/history").json()["items"])


def test_pair_trial_returns_both_sides_and_delta(client):
    r = client.post("/api/bill/pair", json=pair_body())
    assert r.status_code == 200
    data = r.json()
    assert data["persist"] is False
    assert data["left"]["account_id"] == 1
    assert data["left"]["account_name"] == "张家"
    assert data["left"]["total"] == 62.40
    assert data["right"]["account_id"] == 2
    assert data["right"]["total"] == 309.60
    assert data["delta"] == 247.20
    assert len(data["left"]["segments"]) == 1
    assert len(data["right"]["segments"]) == 3


def test_pair_trial_default_writes_nothing(client):
    before = history_count(client)
    r = client.post("/api/bill/pair", json=pair_body())
    assert r.status_code == 200
    assert r.json()["left"]["run_id"] is None
    assert r.json()["right"]["run_id"] is None
    assert history_count(client) == before


def test_pair_persist_writes_two_runs(client):
    before = history_count(client)
    r = client.post("/api/bill/pair", json=pair_body(persist=True))
    assert r.status_code == 200
    data = r.json()
    left_id, right_id = data["left"]["run_id"], data["right"]["run_id"]
    assert left_id is not None and right_id is not None
    assert left_id != right_id
    assert history_count(client) == before + 2
    items = {h["id"]: h for h in client.get("/api/history").json()["items"]}
    for run_id, account_id, side in ((left_id, 1, "left"), (right_id, 2, "right")):
        row = items[run_id]
        assert row["kind"] == "pair_bill"
        assert row["account_id"] == account_id
        assert json.loads(row["input_json"])["side"] == side
        stored = json.loads(row["result_json"])
        if side == "left":
            assert stored["total"] == data[side]["total"]
            assert json.loads(row["input_json"])["kwh"] == data[side]["kwh"]
        else:
            assert stored.get("total") is not None
            assert "kwh" in json.loads(row["input_json"])


def test_pair_missing_account_names_left_side(client):
    before = history_count(client)
    r = client.post("/api/bill/pair", json=pair_body(left={"account_id": 999}, persist=True))
    assert r.status_code == 404
    detail = r.json()["detail"]
    assert detail["side"] == "left"
    assert detail["error"] == "account_not_found"
    assert history_count(client) == before


def test_pair_missing_account_names_right_side(client):
    r = client.post("/api/bill/pair", json=pair_body(right={"account_id": 999}))
    assert r.status_code == 404
    assert r.json()["detail"]["side"] == "right"


def test_pair_invalid_kwh_names_side(client):
    before = history_count(client)
    r = client.post("/api/bill/pair", json=pair_body(right={"kwh": -5}, persist=True))
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["side"] == "right"
    assert detail["error"] == "invalid_kwh"
    r = client.post("/api/bill/pair", json=pair_body(left={"kwh": -1}))
    assert r.status_code == 400
    assert r.json()["detail"]["side"] == "left"
    assert history_count(client) == before


def test_pair_per_side_peak_switch(client):
    r = client.post("/api/bill/pair", json=pair_body(left={"kwh": 400, "peak": True}, right={"kwh": 400, "peak": False}))
    data = r.json()
    assert data["left"]["peak_factor"] == 1.2
    assert data["right"]["peak_factor"] == 1.0
    assert data["delta"] == -51.60
