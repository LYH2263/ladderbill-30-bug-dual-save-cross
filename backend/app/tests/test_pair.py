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
        payload = json.loads(row["input_json"])
        assert payload["side"] == side
        stored = json.loads(row["result_json"])
        # 每条落库运行必须与并列区对应侧完全一致：户号、电量、分段、合计
        assert payload["kwh"] == data[side]["kwh"]
        assert payload["account_id"] == data[side]["account_id"]
        assert stored["account_id"] == account_id
        assert stored["account_name"] == data[side]["account_name"]
        assert stored["kwh"] == data[side]["kwh"]
        assert stored["total"] == data[side]["total"]
        assert stored["segments"] == data[side]["segments"]
        assert stored["peak_factor"] == data[side]["peak_factor"]

    # 直接按编号打开，两侧各自自洽
    left_row = client.get(f"/api/history/{left_id}").json()
    right_row = client.get(f"/api/history/{right_id}").json()
    left_stored = json.loads(left_row["result_json"])
    right_stored = json.loads(right_row["result_json"])
    assert left_stored["total"] == 62.40
    assert right_stored["total"] == 309.60
    assert len(left_stored["segments"]) == 1
    assert len(right_stored["segments"]) == 3


def test_pair_persist_twice_right_uses_its_own_bands(client):
    # 第一次保存：左 120 / 右 400
    first = client.post("/api/bill/pair", json=pair_body(persist=True)).json()
    # 只改右户电量再保存：右 200（落在第二档），左户不动
    second = client.post(
        "/api/bill/pair",
        json=pair_body(right={"kwh": 200, "peak": False}, persist=True),
    ).json()
    items = {h["id"]: h for h in client.get("/api/history").json()["items"]}
    right_stored = json.loads(items[second["right"]["run_id"]]["result_json"])
    # 新右户运行必须是本次右户 200kWh 的结果，不带上一笔左户的分段
    assert right_stored["account_id"] == 2
    assert right_stored["kwh"] == 200
    assert right_stored["total"] == second["right"]["total"]
    assert right_stored["segments"] == second["right"]["segments"]
    assert right_stored["total"] != first["right"]["total"]
    assert right_stored["segments"] != json.loads(
        items[first["left"]["run_id"]]["result_json"]
    )["segments"]
    # 左户运行仍与并列区左侧一致
    left_stored = json.loads(items[second["left"]["run_id"]]["result_json"])
    assert left_stored["total"] == second["left"]["total"]
    assert left_stored["segments"] == second["left"]["segments"]


def test_pair_persist_failure_writes_nothing(client, monkeypatch):
    from app.repositories import runs as runs_repo

    before = history_count(client)
    real_insert = runs_repo.insert
    calls = {"n": 0}

    def flaky_insert(conn, kind, payload, result, account_id=None):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom on right insert")
        return real_insert(conn, kind, payload, result, account_id)

    monkeypatch.setattr(runs_repo, "insert", flaky_insert)
    # TestClient 默认把服务端异常直接抛出；关键是异常后记录条数不变
    with pytest.raises(RuntimeError):
        client.post("/api/bill/pair", json=pair_body(persist=True))
    assert history_count(client) == before


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
