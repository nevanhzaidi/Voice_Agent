from typing import Dict, Any
from config import settings
import base64
import httpx
import json


class VisionService:
    """
    Best-effort vision analysis.

    - If OPENAI_API_KEY is set, uses OpenAI Responses API with an image input.
    - Otherwise raises an exception so callers can fall back gracefully.
    """

    async def analyze_image_bytes(self, image_bytes: bytes) -> Dict[str, Any]:
        if not getattr(settings, "openai_api_key", ""):
            raise RuntimeError("OPENAI_API_KEY not configured.")

        model = getattr(settings, "openai_vision_model", "") or "gpt-4o-mini"
        b64 = base64.b64encode(image_bytes).decode("utf-8")

        prompt = (
            "You are helping troubleshoot home appliances.\n"
            "From the image, identify:\n"
            "1) appliance_type (one of: washer, dryer, refrigerator, dishwasher, oven, hvac, unknown)\n"
            "2) visible_issues (array of short strings)\n"
            "3) helpful_notes (short text)\n"
            "Return ONLY valid JSON with keys: appliance_type, visible_issues, helpful_notes.\n"
        )

        payload = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"},
                    ],
                }
            ],
        }

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()

        # Try to extract output text; if the SDK changes, keep best-effort parsing.
        text = ""
        for item in data.get("output", []) or []:
            for c in item.get("content", []) or []:
                if c.get("type") in ("output_text", "text"):
                    text += c.get("text", "")

        if not text:
            # fallback to legacy key if present
            text = data.get("output_text", "") or ""

        text = text.strip()
        if not text:
            raise RuntimeError("Vision model returned empty response.")

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # If model returned extra text, keep it but still return something useful
            return {
                "appliance_type": "unknown",
                "visible_issues": [],
                "helpful_notes": text,
            }

