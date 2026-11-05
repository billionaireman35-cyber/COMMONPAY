from fastapi import APIRouter, Depends

from app.core.security import require_api_key
from mirror.report import build_report
from mirror.runtime import get_store

router = APIRouter(
    prefix="/reconciliation",
    tags=["Reconciliation"],
    dependencies=[Depends(require_api_key)],
)


@router.get("")
def reconciliation_report():
    # Plain def: FastAPI runs it in a threadpool, so the blocking DB read
    # does not stall the event loop.
    return build_report(get_store())
