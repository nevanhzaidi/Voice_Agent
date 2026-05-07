from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from models.db_operations import DBOperations
import logging
import json as json_module
from services.vapi import VapiService
from interactors.scheduling_interactor import SchedulingInteractor
from interactors.troubleshooting_interactor import TroubleshootingInteractor
from services.email_service import EmailService
from config import settings
from datetime import datetime, timezone
import re


class ConversationInteractor:
    def _normalize_spoken_email(self, raw: str) -> str:
        """
        Normalize common spoken/transcribed email patterns like:
        'a l i at g mail dot com' -> 'ali@gmail.com'
        """
        s = (raw or "").strip().lower()
        if not s:
            return ""

        # Common word replacements
        s = re.sub(r"\s+at\s+", "@", s)
        s = re.sub(r"\s+dot\s+", ".", s)
        s = s.replace(" at ", "@").replace(" dot ", ".")
        s = s.replace("(at)", "@").replace("[at]", "@").replace("{at}", "@")
        s = s.replace("(dot)", ".").replace("[dot]", ".").replace("{dot}", ".")

        # Remove spaces around separators
        s = re.sub(r"\s*@\s*", "@", s)
        s = re.sub(r"\s*\.\s*", ".", s)

        # If it's spelled out with spaces between characters, collapse spaces
        # but keep single '@' and '.' intact.
        s = re.sub(r"\s+", "", s)

        # Fix common "gmail" splits like g mail -> gmail (after space removal this becomes gmail anyway)
        s = s.replace("gmai1", "gmail")  # occasional STT confusion

        return s

    def handle_call_started(self, db: Session, call_id: str, caller_phone: Optional[str]) -> Dict[str, Any]:
        log = DBOperations().get_call_log(db, call_id)
        if not log:
            DBOperations().create_call_log(db, call_id, caller_phone)
        return {"status": "call_started", "call_id": call_id}

    def handle_call_ended(
        self,
        db: Session,
        call_id: str,
        summary: Optional[str] = None,
        full_transcript: Optional[str] = None,
    ) -> Dict[str, Any]:
        updates: Dict[str, Any] = {
            "status": "pending",
            "ended_at": datetime.now(timezone.utc),
            "conversation_summary": summary,
        }
        if full_transcript:
            log = DBOperations().get_call_log(db, call_id)
            existing_extra = log.extra_data or {} if log else {}
            existing_extra["full_transcript"] = full_transcript
            updates["extra_data"] = existing_extra

        DBOperations().update_call_log(db, call_id, updates)
        return {"status": "call_ended", "call_id": call_id}

    def handle_transcript(
        self,
        db: Session,
        call_id: str,
        transcript_text: str,
        messages: List[Dict] = None,
    ) -> Dict[str, Any]:
        if messages is None:
            messages = []

        log = DBOperations().get_call_log(db, call_id)
        if not log:
            log = DBOperations().create_call_log(db, call_id, None)

        extra = log.extra_data or {}

        if messages:
            extra["messages"] = messages
            customer_msgs = [m for m in messages if m.get("role") == "user"]
            if customer_msgs:
                extra["last_customer_message"] = customer_msgs[-1].get("content", "")
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            if assistant_msgs:
                extra["last_agent_message"] = assistant_msgs[-1].get("content", "")

        if transcript_text:
            extra["live_transcript"] = transcript_text

        DBOperations().update_call_log(db, call_id, {"extra_data": extra})
        return {"status": "transcript_saved"}

    def handle_tool_call(self, db: Session, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "find_technician":
            return SchedulingInteractor().find_technicians_for_call(
                db,
                tool_args.get("zip_code", ""),
                tool_args.get("appliance_type", ""),
            )

        elif tool_name == "book_appointment":
            return SchedulingInteractor().book_appointment_from_call(db, tool_args)

        elif tool_name == "get_troubleshooting_steps":
            return TroubleshootingInteractor().get_troubleshooting_steps(
                tool_args.get("appliance_type", ""),
                tool_args.get("symptoms", ""),
            )

        elif tool_name == "update_call_context":
            call_id = tool_args.get("call_id", "")
            DBOperations().update_call_log(db, call_id, {
                "appliance_type": tool_args.get("appliance_type"),
                "zip_code": tool_args.get("zip_code"),
                "customer_name": tool_args.get("customer_name"),
            })
            return {"status": "updated"}

        elif tool_name == "request_image_upload":
            call_id = tool_args.get("call_id", "")
            email_raw = (tool_args.get("email") or "").strip()
            email = self._normalize_spoken_email(email_raw)
            if not email:
                return {"success": False, "message": "Missing email."}
            if "@" not in email or "." not in email.split("@")[-1]:
                return {"success": False, "message": f"Invalid email: {email_raw}"}

            vu = DBOperations().create_visual_upload(db, email=email, call_id=call_id or None)
            upload_url = f"{settings.backend_url.rstrip('/')}/visual/upload/{vu.token}"

            # Persist on call log too (best effort)
            if call_id:
                log = DBOperations().get_call_log(db, call_id)
                extra = (log.extra_data or {}) if log else {}
                extra["customer_email"] = email
                extra["visual_upload_token"] = vu.token
                extra["visual_upload_url"] = upload_url
                DBOperations().update_call_log(db, call_id, {"extra_data": extra})

            # Send email if configured; otherwise return link so the agent can read it out.
            send_result = {}
            try:
                send_result = EmailService().send_upload_link(to_email=email, upload_url=upload_url)
            except Exception as e:
                send_result = {"sent": False, "error": str(e), "upload_url": upload_url}

            return {
                "success": True,
                "token": vu.token,
                "upload_url": upload_url,
                "email_result": send_result,
            }

        elif tool_name == "get_visual_upload_status":
            token = (tool_args.get("token") or "").strip()
            if not token:
                return {"success": False, "message": "Missing token."}

            vu = DBOperations().get_visual_upload_by_token(db, token)
            if not vu:
                return {"success": False, "message": "Not found."}

            return {
                "success": True,
                "token": vu.token,
                "status": vu.status,
                "email": vu.email,
                "call_id": vu.call_id,
                "analysis": vu.analysis,
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def process_webhook(self, db: Session, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for Vapi webhooks. Extracts data and routes to specific handlers.
        """
        
        logger = logging.getLogger(__name__)
        message = payload.get("message", {})
        event_type = message.get("type", payload.get("type", "unknown"))

        call_data = message.get("call") or payload.get("call") or {}
        call_id = call_data.get("id", "")
        if not call_id:
            call_id = message.get("callId", "") or payload.get("callId", "")
        if not call_id:
            call_id = payload.get("id", "")

        caller_phone = (
            call_data.get("customer", {}).get("number", "")
            or call_data.get("phoneNumber", {}).get("number", "")
            or message.get("customer", {}).get("number", "")
            or ""
        )

        logger.info(f"═══ VAPI WEBHOOK ═══")
        logger.info(f"  Event: {event_type}")
        logger.info(f"  Call ID: {call_id or 'EMPTY'}")
        logger.info(f"  Phone: {caller_phone or 'EMPTY'}")

        if call_id:
            self.handle_call_started(db, call_id, caller_phone)

        if event_type in ("call-started", "status-update"):
            return {"status": "ok"}

        elif event_type in ("call-ended", "end-of-call-report"):
            parsed = VapiService().parse_webhook(payload)
            summary = parsed.get("summary")
            full_transcript = message.get("artifact", {}).get("transcript", "")
            self.handle_call_ended(db, call_id, summary, full_transcript)
            return {"status": "ok"}

        elif event_type == "tool-calls":
            parsed = VapiService().parse_webhook(payload)
            tool_calls = parsed.get("tool_calls", [])
            if not tool_calls:
                tool_calls = message.get("toolCallList", [])
            if not tool_calls:
                return {"status": "no_tool_calls"}

            tool_call = tool_calls[0]
            tool_call_id = tool_call.get("id", "")
            tool_name = tool_call.get("function", {}).get("name", "")
            tool_args_raw = tool_call.get("function", {}).get("arguments", {})

            if isinstance(tool_args_raw, str):
                tool_args = json_module.loads(tool_args_raw)
            else:
                tool_args = tool_args_raw

            tool_args["call_id"] = call_id
            logger.info(f"  Tool call: {tool_name}({tool_args})")
            result = self.handle_tool_call(db, tool_name, tool_args)
            return VapiService().build_tool_result_response(tool_call_id, result)

        elif event_type in ("transcript", "conversation-update"):
            parsed = VapiService().parse_webhook(payload)
            transcript_text = parsed.get("transcript", "")
            messages = message.get("conversation", [])
            if transcript_text or messages:
                self.handle_transcript(db, call_id, transcript_text, messages)
            return {"status": "ok"}

        elif event_type == "assistant-request":
            return {"status": "ok"}

        else:
            if message.get("transcript"):
                parsed = VapiService().parse_webhook(payload)
                self.handle_transcript(db, call_id, parsed.get("transcript", ""), [])
            return {"status": "ok"}
