"""
backend/services/alert_service.py
==================================
Real alert system for emergency routing decisions.

Channels:
  1. Telegram Bot (instant push to doctor's phone)
  2. Email via SMTP (Gmail App Password or any SMTP)

Both channels are sent concurrently on every EDGE override (criticality >= 9.0).
Falls back gracefully if not configured — logs a warning but does not crash.

Setup:
  TELEGRAM_BOT_TOKEN = from @BotFather on Telegram
  TELEGRAM_CHAT_ID   = your group/personal chat ID (get via @userinfobot)
  EMAIL_USERNAME     = your Gmail address
  EMAIL_PASSWORD     = Gmail App Password (not your main password)
                       Google Account → Security → App Passwords
"""

import asyncio
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)


# ── Telegram ──────────────────────────────────────────────────────────────────
async def send_telegram_alert(
    device_id: str,
    criticality: float,
    predicted_latency_ms: float,
    reason: str,
    timestamp: Optional[str] = None,
) -> bool:
    """
    Send an emergency alert to the configured Telegram chat.

    Returns True if sent successfully, False otherwise.
    Never raises — failure is logged as a warning.
    """
    if not settings.telegram_configured:
        logger.debug("[alert] Telegram not configured — skipping")
        return False

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    risk_emoji = "🔴" if criticality >= 9.0 else "🟠"

    message = (
        f"{risk_emoji} *EMERGENCY ALERT — TELEMEDICINE SYSTEM*\n\n"
        f"📟 *Device:*      `{device_id}`\n"
        f"🚨 *Criticality:* `{criticality:.1f}/10`\n"
        f"📡 *Latency:*     `{predicted_latency_ms:.1f} ms`\n"
        f"📋 *Reason:*      `{reason}`\n"
        f"🕐 *Time:*        `{ts}`\n\n"
        f"⚕️ _On-call physician: please respond immediately._"
    )

    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    settings.TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "Markdown",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("[alert] Telegram alert sent to chat_id=%s for device=%s",
                        settings.TELEGRAM_CHAT_ID, device_id)
            return True
    except Exception as exc:
        logger.warning("[alert] Telegram alert FAILED for device=%s: %s", device_id, exc)
        return False


# ── Email ─────────────────────────────────────────────────────────────────────
async def send_email_alert(
    device_id: str,
    criticality: float,
    predicted_latency_ms: float,
    reason: str,
    timestamp: Optional[str] = None,
) -> bool:
    """
    Send an emergency alert email via SMTP.
    Runs in a thread pool to avoid blocking the async event loop.

    Returns True if sent successfully, False otherwise.
    Never raises.
    """
    if not settings.email_configured:
        logger.debug("[alert] Email not configured — skipping")
        return False

    ts = timestamp or datetime.now(timezone.utc).isoformat()

    subject = f"🚨 EMERGENCY ALERT — Device {device_id} (Criticality {criticality:.1f}/10)"

    html_body = f"""
    <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
      <div style="background: #c0392b; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin:0;">🚨 Emergency Medical Alert</h2>
        <p style="margin:4px 0 0 0; opacity:0.85;">Telemedicine Workload Offloader</p>
      </div>
      <div style="background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; border: 1px solid #ddd;">
        <table style="width:100%; border-collapse:collapse;">
          <tr><td style="padding:8px; font-weight:bold; width:40%;">Device ID</td>
              <td style="padding:8px; font-family:monospace;">{device_id}</td></tr>
          <tr style="background:#fff3f3;"><td style="padding:8px; font-weight:bold;">Criticality Score</td>
              <td style="padding:8px; color:#c0392b; font-size:1.2em; font-weight:bold;">{criticality:.1f} / 10.0</td></tr>
          <tr><td style="padding:8px; font-weight:bold;">Predicted Latency</td>
              <td style="padding:8px;">{predicted_latency_ms:.1f} ms</td></tr>
          <tr style="background:#fff3f3;"><td style="padding:8px; font-weight:bold;">Alert Reason</td>
              <td style="padding:8px;">{reason}</td></tr>
          <tr><td style="padding:8px; font-weight:bold;">Timestamp</td>
              <td style="padding:8px;">{ts}</td></tr>
        </table>
        <div style="margin-top:16px; padding:12px; background:#fff3cd; border-radius:4px; border-left:4px solid #f39c12;">
          <strong>⚕️ Action Required:</strong> On-call physician must respond immediately.
          Patient data is being routed to the local EDGE node for immediate processing.
        </div>
      </div>
    </body></html>
    """

    def _send_sync():
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = settings.EMAIL_FROM
        msg["To"]      = settings.EMAIL_USERNAME
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, settings.EMAIL_USERNAME, msg.as_string())

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync)
        logger.info("[alert] Email alert sent to %s for device=%s", settings.EMAIL_USERNAME, device_id)
        return True
    except Exception as exc:
        logger.warning("[alert] Email alert FAILED for device=%s: %s", device_id, exc)
        return False


# ── Combined alert ────────────────────────────────────────────────────────────
async def send_emergency_alert(
    device_id: str,
    criticality: float,
    predicted_latency_ms: float,
    reason: str,
    timestamp: Optional[str] = None,
) -> dict:
    """
    Send alerts via ALL configured channels concurrently.
    Returns a summary of which channels succeeded.

    Called by edge_node when routing_decision == EDGE and reason == override_critical_patient.
    """
    telegram_ok, email_ok = await asyncio.gather(
        send_telegram_alert(device_id, criticality, predicted_latency_ms, reason, timestamp),
        send_email_alert(device_id, criticality, predicted_latency_ms, reason, timestamp),
    )

    result = {
        "telegram": telegram_ok,
        "email":    email_ok,
        "any_sent": telegram_ok or email_ok,
    }

    if not result["any_sent"]:
        logger.warning(
            "[alert] No alert channels configured or all failed for device=%s! "
            "Set TELEGRAM_BOT_TOKEN / EMAIL_USERNAME in .env",
            device_id,
        )

    return result
