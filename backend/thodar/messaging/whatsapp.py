"""WhatsApp Cloud API (Meta). Without a token, messages are recorded in `outbox` instead of sent,
which is how tests and the offline demo run.

Note: business-initiated messages outside the 24-hour window must use a pre-approved utility
template in production; `send_buttons` is the in-window / test-number path.
"""

import logging
from dataclasses import dataclass

import httpx

from thodar.config import get_settings

log = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


@dataclass
class Incoming:
    phone: str  # 10 digits
    kind: str  # text | button | audio
    text: str | None = None
    button_id: str | None = None
    media_id: str | None = None


class WhatsAppClient:
    def __init__(self, token: str | None = None, phone_number_id: str | None = None, sink=None):
        """`sink(payload)` is called for every message in dry-run mode (e.g. to persist the demo outbox)."""
        s = get_settings()
        self.sink = sink
        self.token = token if token is not None else s.whatsapp_token
        self.phone_number_id = phone_number_id or s.whatsapp_phone_number_id
        self.outbox: list[dict] = []

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.phone_number_id)

    def _post(self, payload: dict) -> dict:
        if not self.enabled:
            self.outbox.append(payload)
            if self.sink:
                self.sink(payload)
            log.info("whatsapp dry-run to %s", payload.get("to"))
            return {"dry_run": True}
        r = httpx.post(f"{GRAPH}/{self.phone_number_id}/messages", json=payload,
                       headers={"Authorization": f"Bearer {self.token}"}, timeout=20)
        r.raise_for_status()
        return r.json()

    def send_text(self, phone: str, body: str) -> dict:
        return self._post({"messaging_product": "whatsapp", "to": f"91{phone}", "type": "text",
                           "text": {"body": body}})

    def send_buttons(self, phone: str, body: str, buttons: list[tuple[str, str]]) -> dict:
        return self._post({
            "messaging_product": "whatsapp", "to": f"91{phone}", "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {"buttons": [{"type": "reply", "reply": {"id": i, "title": t[:20]}} for i, t in buttons]},
            },
        })

    def download_media(self, media_id: str) -> bytes | None:
        if not self.enabled:
            return None
        h = {"Authorization": f"Bearer {self.token}"}
        meta = httpx.get(f"{GRAPH}/{media_id}", headers=h, timeout=20).json()
        return httpx.get(meta["url"], headers=h, timeout=30).content


def parse_webhook(payload: dict) -> list[Incoming]:
    """Pulls the messages we care about out of a Cloud API webhook body."""
    out: list[Incoming] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for m in change.get("value", {}).get("messages", []):
                phone = m.get("from", "")[-10:]
                t = m.get("type")
                if t == "text":
                    out.append(Incoming(phone, "text", text=m["text"]["body"]))
                elif t == "interactive" and m["interactive"].get("type") == "button_reply":
                    reply = m["interactive"]["button_reply"]
                    out.append(Incoming(phone, "button", text=reply.get("title"), button_id=reply["id"]))
                elif t == "button":  # quick reply on a template message
                    out.append(Incoming(phone, "button", text=m["button"].get("text"),
                                        button_id=m["button"].get("payload")))
                elif t == "audio":
                    out.append(Incoming(phone, "audio", media_id=m["audio"]["id"]))
    return out
