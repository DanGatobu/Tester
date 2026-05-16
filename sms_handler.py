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
