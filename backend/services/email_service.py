from typing import Dict, Any
from config import settings
import httpx


class EmailService:
    """
    Sends email via Resend if configured.
    If not configured, returns a "not sent" result but still includes the link
    (useful for local testing).
    """

    def send_upload_link(self, *, to_email: str, upload_url: str) -> Dict[str, Any]:
        if not settings.resend_api_key or not settings.email_from:
            return {
                "sent": False,
                "provider": None,
                "message": "Email provider not configured. Set RESEND_API_KEY and EMAIL_FROM.",
                "upload_url": upload_url,
            }

        payload = {
            "from": settings.email_from,
            "to": [to_email],
            "subject": "AppliFix: Upload a photo for diagnosis",
            "html": f"""
              <div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif;">
                <p>Thanks for calling AppliFix.</p>
                <p>Please upload a photo of your appliance using this secure link:</p>
                <p><a href="{upload_url}">{upload_url}</a></p>
                <p>This link is unique to your case.</p>
              </div>
            """,
        }

        headers = {
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
        }

        with httpx.Client(timeout=20) as client:
            r = client.post("https://api.resend.com/emails", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        return {"sent": True, "provider": "resend", "id": data.get("id"), "upload_url": upload_url}

