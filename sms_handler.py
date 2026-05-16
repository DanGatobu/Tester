"""
sms_handler.py — Dev 4: The SMS Handler
==========================================
Sends role-aware "handshake" SMS to both parties once a match is found.
"""
import logging
import africastalking
from config import AT_USERNAME, AT_API_KEY, AT_SENDER_ID

log = logging.getLogger(__name__)
africastalking.initialize(AT_USERNAME, AT_API_KEY)
sms = africastalking.SMS


def send_match_sms(caller_phone: str, matches: list[dict], user_type: str = "job_seeker") -> bool:
    if not matches:
        return False

    top     = matches[0]
    success = True

    if user_type == "employer":
        # ── Employer found a job seeker ───────────────────────────────────────
        caller_msg = (
            f"🔧 Jua Kali Matcher\n"
            f"Hi! We found a match for your job listing:\n"
            f"Name: {top['name'] or 'N/A'}\n"
            f"Trade: {top['trade']}\n"
            f"Location: {top['location']}\n"
            f"Contact: {top['phone']}\n"
            f"Tell them Jua Kali sent you! 💪"
        )
        match_msg = (
            f"🔧 Jua Kali Matcher\n"
            f"Good news! An employer is looking for your skills!\n"
            f"They need: {top['trade']}\n"
            f"In: {top['location']}\n"
            f"They will contact you on: {caller_phone}\n"
            f"Be ready! 💪"
        )
    else:
        # ── Job seeker found an employer or master ────────────────────────────
        caller_msg = (
            f"🔧 Jua Kali Matcher\n"
            f"Great news! We found your match:\n"
            f"Name: {top['name'] or 'N/A'}\n"
            f"Trade: {top['trade']}\n"
            f"Location: {top['location']}\n"
            f"Contact: {top['phone']}\n"
            f"Tell them Jua Kali sent you! 💪"
        )
        match_msg = (
            f"🔧 Jua Kali Matcher\n"
            f"A job seeker matched your listing!\n"
            f"Trade: {top['trade']}\n"
            f"They will contact you on: {caller_phone}\n"
            f"Good luck! 💪"
        )

    success &= _send(caller_phone, caller_msg)
    success &= _send(top["phone"], match_msg)
    return success


def send_match_notification(notify_phone: str, profile: dict,
                            matches: list[dict], user_type: str = "job_seeker") -> bool:
    """Send a single 'we found a match' SMS to the number the caller asked
    to be notified on (used by the web simulator wizard)."""
    if not notify_phone or not matches:
        return False

    top  = matches[0]
    name = (profile or {}).get("name") or "there"

    if user_type == "employer":
        msg = (
            f"🔧 Jua Kali Matcher\n"
            f"Hi {name}! We found a worker for your job:\n"
            f"Name: {top.get('name') or 'N/A'}\n"
            f"Skill: {top.get('trade') or 'N/A'}\n"
            f"Location: {top.get('location') or 'N/A'}\n"
            f"Contact: {top.get('phone') or 'N/A'}\n"
            f"Tell them Jua Kali sent you! 💪"
        )
    else:
        msg = (
            f"🔧 Jua Kali Matcher\n"
            f"Hi {name}! We found a match for you:\n"
            f"Name: {top.get('name') or 'N/A'}\n"
            f"Trade: {top.get('trade') or 'N/A'}\n"
            f"Location: {top.get('location') or 'N/A'}\n"
            f"Contact: {top.get('phone') or 'N/A'}\n"
            f"Tell them Jua Kali sent you! 💪"
        )

    return _send(notify_phone, msg)


def _send(phone: str, message: str) -> bool:
    try:
        resp       = sms.send(message, [phone], sender_id=AT_SENDER_ID)
        recipients = resp.get("SMSMessageData", {}).get("Recipients", [])
        if recipients:
            status = recipients[0].get("status", "")
            log.info("SMS → %s: %s", phone, status)
            return status in ("Success", "Sent")
        return False
    except Exception as e:
        log.error("SMS failed to %s: %s", phone, e)
        return False
