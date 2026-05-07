from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from database.session import get_db
from interactors.conversation_interactor import ConversationInteractor
import logging
import json

router = APIRouter(prefix="/vapi", tags=["vapi"])
logger = logging.getLogger(__name__)

@router.post("/webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):

    try:
        payload = await request.json()

        # Defensive: a client can send a JSON string (e.g. "hello") instead of an object.
        # Vapi webhooks are expected to be JSON objects.
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON string payload: {e.msg}") from e

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Webhook payload must be a JSON object.")

        return ConversationInteractor().process_webhook(db, payload)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vapi webhook error: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}
