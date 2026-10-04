import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.utils import timezone

from .summary_services import daily_summary


def answer_with_model(*, prompt, organization, user):
    """Ask the internal model for a read-only answer using curated workspace context."""
    base_url = os.environ.get("EVOLVE_AI_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("EVOLVE_AI_MODEL", "qwen3:8b").strip()
    if not base_url or not model:
        return None

    context = daily_summary(user=user, organization=organization)
    context_text = json.dumps(context, default=str, separators=(",", ":"))[:12000]
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are Evolve's workspace assistant. Answer only from the supplied "
                    "workspace context. Do not invent records, permissions, email content, "
                    "credentials, or actions. You are read-only: never claim to create, "
                    "delete, send, approve, or change anything. Keep the answer concise. "
                    f"Current date: {timezone.localdate().isoformat()}."
                ),
            },
            {
                "role": "user",
                "content": f"Workspace context:\n{context_text}\n\nQuestion: {prompt}",
            },
        ],
        "options": {"temperature": 0.2},
    }
    try:
        request = Request(
            f"{base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
        answer = str(payload.get("message", {}).get("content", "")).strip()
        return answer[:4000] if answer else None
    except (OSError, URLError, TimeoutError, ValueError, KeyError):
        return None
