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
        stored_input = json.loads(row["input_json"])
        assert stored_input["side"] == side
        assert stored_input["kwh"] == data[side]["kwh"]
        stored = json.loads(row["result_json"])
        assert stored["total"] == data[side]["total"]
        assert stored["kwh"] == data[side]["kwh"]
        assert stored["segments"] == data[side]["segments"]
        assert stored["account_id"] == account_id
        assert stored["peak_factor"] == data[side]["peak_factor"]


def test_pair_persist_right_run_matches_right_side_when_reopened(client):
    r = client.post("/api/bill/pair", json=pair_body(persist=True))
    data = r.json()
    for side in ("left", "right"):
        run_id = data[side]["run_id"]
        reopened = client.get(f"/api/history/{run_id}").json()
        stored = json.loads(reopened["result_json"])
        assert stored["account_id"] == data[side]["account_id"]
        assert stored["account_name"] == data[side]["account_name"]
        assert stored["kwh"] == data[side]["kwh"]
        assert stored["total"] == data[side]["total"]
        assert stored["segments"] == data[side]["segments"]


def test_pair_persist_then_change_only_right_keeps_own_bands(client):
    first = client.post("/api/bill/pair", json=pair_body(persist=True)).json()
    before = history_count(client)
    second = client.post(
        "/api/bill/pair",
        json=pair_body(right={"kwh": 260, "peak": False}, persist=True),
    ).json()
    assert history_count(client) == before + 2
    # 右户新运行必须是本次右户电量（260、不尖峰）的分段，而不是上一笔左户的
    right_run = client.get(f"/api/history/{second['right']['run_id']}").json()
    stored = json.loads(right_run["result_json"])
    assert stored["account_id"] == 2
    assert stored["kwh"] == 260
    assert stored["peak_factor"] == 1.0
    assert stored["total"] == second["right"]["total"]
    assert stored["segments"] == second["right"]["segments"]
    assert stored["segments"] != first["left"]["segments"]
    # 左户新运行仍是左户自己的数据
    left_run = client.get(f"/api/history/{second['left']['run_id']}").json()
    left_stored = json.loads(left_run["result_json"])
    assert left_stored["account_id"] == 1
    assert left_stored["total"] == second["left"]["total"]
    assert left_stored["segments"] == second["left"]["segments"]


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
