import math

from app.db import connect
from app.engines.pair_compare import compare_pair
from app.engines.peak_compare import compare_plain_vs_peak
from app.engines.tier_progressive import calc_bill
from app.repositories import accounts as accounts_repo
from app.repositories import readings as readings_repo
from app.repositories import runs as runs_repo
from app.repositories import settings as settings_repo
from app.repositories import tiers as tiers_repo


class SideError(Exception):
    """One side of a pair trial failed validation; carries the failing side tag."""

    def __init__(self, side: str, error: str, message: str, status: int = 400):
        super().__init__(message)
        self.side = side
        self.error = error
        self.message = message
        self.status = status


class BillingService:
    def __init__(self):
        self._conn = connect()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def list_accounts(self):
        return accounts_repo.list_all(self._conn)

    def get_account(self, account_id: int):
        return accounts_repo.get(self._conn, account_id)

    def list_tiers(self):
        return tiers_repo.list_ordered(self._conn)

    def list_readings(self):
        return readings_repo.list_all(self._conn)

    def readings_for_account(self, account_id: int):
        return readings_repo.for_account(self._conn, account_id)

    def settings_map(self):
        return settings_repo.get_map(self._conn)

    def run_bill(self, kwh: float, peak: bool, account_id: int | None, persist: bool):
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        factor = pf if peak else 1.0
        result = calc_bill(kwh, tiers, factor)
        run_id = None
        if persist:
            run_id = runs_repo.insert(
                self._conn,
                "bill",
                {"kwh": kwh, "peak": peak, "account_id": account_id},
                result,
                account_id,
            )
        return {"run_id": run_id, **result}

    def run_compare(self, kwh: float, persist: bool):
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        result = compare_plain_vs_peak(kwh, tiers, pf)
        run_id = None
        if persist:
            run_id = runs_repo.insert(self._conn, "compare", {"kwh": kwh}, result, None)
        return {"run_id": run_id, **result}

    def run_pair(self, left, right, persist: bool):
        accounts = {}
        for key, side in (("left", left), ("right", right)):
            if not math.isfinite(side.kwh) or side.kwh < 0:
                raise SideError(key, "invalid_kwh", f"电量非法：{side.kwh}")
            acct = accounts_repo.get(self._conn, side.account_id)
            if not acct:
                raise SideError(key, "account_not_found", f"户号 {side.account_id} 不存在", 404)
            accounts[key] = acct
        tiers = tiers_repo.as_calc_rows(self._conn)
        pf = settings_repo.peak_factor(self._conn)
        result = compare_pair(
            {"kwh": left.kwh, "peak": left.peak},
            {"kwh": right.kwh, "peak": right.peak},
            tiers,
            pf,
        )
        for key, side in (("left", left), ("right", right)):
            result[key].update(
                {
                    "account_id": accounts[key]["id"],
                    "account_name": accounts[key]["name"],
                    "peak": side.peak,
                    "run_id": None,
                }
            )
        if persist:
            try:
                result["left"]["run_id"] = runs_repo.insert(
                    self._conn,
                    "pair_bill",
                    {"kwh": left.kwh, "peak": left.peak, "account_id": left.account_id, "side": "left"},
                    result["left"],
                    left.account_id,
                    commit=False,
                )
                result["right"]["run_id"] = runs_repo.insert(
                    self._conn,
                    "pair_bill",
                    {"kwh": right.kwh, "peak": right.peak, "account_id": right.account_id, "side": "right"},
                    result["right"],
                    right.account_id,
                    commit=False,
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return {"persist": persist, "delta": result["delta"], "left": result["left"], "right": result["right"]}

    def list_history(self, limit: int = 50):
        return runs_repo.list_recent(self._conn, limit)

    def get_run(self, run_id: int):
        return runs_repo.get(self._conn, run_id)

    def dashboard_stats(self):
        accounts = accounts_repo.list_all(self._conn)
        readings = readings_repo.list_all(self._conn)
        clean = [a for a in accounts if "种子" not in a.get("name", "")]
        dirty = [a for a in accounts if "种子" in a.get("name", "")]
        return {
            "account_count": len(accounts),
            "reading_count": len(readings),
            "clean_accounts": len(clean),
            "dirty_accounts": len(dirty),
            "recent_runs": len(runs_repo.list_recent(self._conn, 5)),
        }
