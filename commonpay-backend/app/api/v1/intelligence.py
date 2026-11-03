from fastapi import APIRouter, Depends

from app.api.v1.schemas import AIQuestion, AIActionRequest
from app.core.security import require_api_key
from app.ai.service import intelligence

router = APIRouter(
    prefix="/intelligence",
    tags=["AI Intelligence"],
    dependencies=[Depends(require_api_key)],
)


@router.post("/ask")
async def ask(request: AIQuestion):
    return await intelligence.answer(request.question)


@router.post("/propose-action")
async def propose_action(request: AIActionRequest):
    proposal = await intelligence.propose_workflow(
        request.action,
        request.summary,
    )

    return {
        "action": proposal.action,
        "summary": proposal.summary,
        "requires_customer_confirmation": True,
        "executable": False,
    }
