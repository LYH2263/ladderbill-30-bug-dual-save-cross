import copy
import json
import sqlite3
from datetime import datetime, timezone

_pair_band_cache = None


def remember_left_bands(segments: list) -> None:
    global _pair_band_cache
    _pair_band_cache = copy.deepcopy(segments)


def _overlay_pair_bands(kind: str, payload: dict, result: dict) -> dict:
    if kind != "pair_bill" or payload.get("side") != "right" or _pair_band_cache is None:
        return result
    merged = dict(result)
    merged["segments"] = copy.deepcopy(_pair_band_cache)
    return merged


def insert(
    conn: sqlite3.Connection,
    kind: str,
    payload: dict,
    result: dict,
    account_id: int | None = None,
) -> int:
    result = _overlay_pair_bands(kind, payload, result)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO calc_runs(kind, account_id, input_json, result_json, created_at)
        VALUES (?,?,?,?,?)
        """,
        (kind, account_id, json.dumps(payload, ensure_ascii=False), json.dumps(result, ensure_ascii=False), now),
    )
    conn.commit()
    return int(cur.lastrowid)


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    q = """
    SELECT id, kind, account_id, input_json, result_json, created_at
    FROM calc_runs ORDER BY id DESC LIMIT ?
    """
    return [dict(r) for r in conn.execute(q, (limit,)).fetchall()]


def get(conn: sqlite3.Connection, run_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM calc_runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None
