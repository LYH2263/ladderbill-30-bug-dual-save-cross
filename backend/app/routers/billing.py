from fastapi import APIRouter, HTTPException

from app.schemas.billing import BillRequest, CompareRequest, PairBillRequest
from app.services.billing_service import BillingService, SideError

router = APIRouter(tags=["billing"])


@router.post("/bill")
def post_bill(body: BillRequest):
    with BillingService() as svc:
        return svc.run_bill(body.kwh, body.peak, body.account_id, body.persist)


@router.post("/compare")
def post_compare(body: CompareRequest):
    with BillingService() as svc:
        return svc.run_compare(body.kwh, body.persist)


@router.post("/bill/pair")
def post_pair_bill(body: PairBillRequest):
    with BillingService() as svc:
        try:
            return svc.run_pair(body.left, body.right, body.persist)
        except SideError as exc:
            raise HTTPException(
                exc.status,
                detail={"side": exc.side, "error": exc.error, "message": exc.message},
            ) from exc
