"""Telegram Bot HTTP API notifier - plain httpx POST, no heavy library needed."""
from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send text to a Telegram chat. Splits messages over Telegram's 4096-char limit."""
    if not bot_token or not chat_id:
        logger.warning("Telegram bot_token/chat_id not configured - skipping send")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = [text[i : i + TELEGRAM_MESSAGE_LIMIT] for i in range(0, len(text), TELEGRAM_MESSAGE_LIMIT)] or [text]

    ok = True
    for chunk in chunks:
        try:
            resp = httpx.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=15.0)
            resp.raise_for_status()
        except Exception:
            logger.exception("Failed to send Telegram message")
            ok = False
    return ok
