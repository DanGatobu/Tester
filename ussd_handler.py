"""
ussd_handler.py — Dev 2: The USSD Lead
========================================
Handles Africa's Talking USSD callback.
Session flow for YOUTH registration:

  CON Welcome to Jua Kali Matcher
  1. Register as Youth
  2. Register as Master
  3. Find my Match

  [Youth path]
  Enter your name → location → trade interest → skill level
  → CON "Matching you..." → END with top match
"""
import json
import logging

from database import get_session, Youth
from matching_engine import find_matches

log = logging.getLogger(__name__)


def handle_ussd(session_id: str, phone: str, text: str, service_code: str) -> str:
    """
    Entry point called by Flask route /ussd
    Returns Africa's Talking response string starting with CON or END.
    """
    session = get_session()
    try:
        youth = session.query(Youth).filter_by(phone=phone).first()
        if not youth:
            youth = Youth(phone=phone, session_data="{}")
            session.add(youth)
            session.commit()

        state = json.loads(youth.session_data or "{}")

        # Split on * to get navigation steps
        parts = [p for p in text.split("*") if p != ""] if text else []

        response = _route(parts, state, youth, phone, session)

        youth.session_data = json.dumps(state)
        session.commit()
        return response

    finally:
        session.close()


def _route(parts: list, state: dict, youth, phone: str, session) -> str:
    depth = len(parts)

    # ── Root menu ─────────────────────────────────────────────────────────────
    if depth == 0:
        state.clear()
        return (
            "CON Welcome to Jua Kali Matcher 🔧\n"
            "Connecting Youth to Master Artisans\n\n"
            "1. Register as Youth\n"
            "2. I am a Master Artisan\n"
            "3. Find my match\n"
            "0. Exit"
        )

    choice = parts[0]

    # ── Exit ──────────────────────────────────────────────────────────────────
    if choice == "0":
        return "END Asante! Thank you for using Jua Kali Matcher. 🙏"

    # ── YOUTH registration flow ───────────────────────────────────────────────
    if choice == "1":
        if depth == 1:
            return "CON Enter your full name:"

        if depth == 2:
            return "CON Enter your town or county\n(e.g. Nairobi, Kisumu, Mombasa):"

        if depth == 3:
            return (
                "CON Choose your trade interest:\n"
                "1. Welding\n"
                "2. Tailoring\n"
                "3. Plumbing\n"
                "4. Carpentry\n"
                "5. Hairdressing\n"
                "6. Motorcycle Repair\n"
                "7. Masonry\n"
                "8. Other (type below)"
            )

        if depth == 4:
            return (
                "CON Your skill level:\n"
                "1. Complete Beginner\n"
                "2. Some experience\n"
                "3. Intermediate"
            )

        if depth == 5:
            name     = parts[1].strip()
            location = parts[2].strip()
            trade_map = {
                "1": "welding", "2": "tailoring", "3": "plumbing",
                "4": "carpentry", "5": "hairdressing", "6": "motorcycle repair",
                "7": "masonry",
            }
            trade = trade_map.get(parts[3], parts[3].strip().lower())
            level_map = {"1": "beginner", "2": "some experience", "3": "intermediate"}
            skill = level_map.get(parts[4], "beginner")

            # Save to DB
            youth.name        = name
            youth.location    = location
            youth.trade       = trade
            youth.skill_level = skill
            session.commit()

            # Run matching
            try:
                matches = find_matches(phone)
            except Exception as e:
                log.error("Matching failed: %s", e)
                matches = []

            if not matches:
                return (
                    f"END Hi {name}! ✅ Registered.\n"
                    "No exact matches yet — we'll SMS you when one is found!\n"
                    "Jua Kali Matcher 🔧"
                )

            top = matches[0]
            return (
                f"END Hi {name}! ✅ Match Found!\n\n"
                f"🔧 Master: {top['name']}\n"
                f"📍 Location: {top['location']}\n"
                f"🛠 Trade: {top['trade']}\n"
                f"📞 {top['phone']}\n\n"
                f"An SMS has been sent to both of you.\n"
                "Jua Kali Matcher 🔧"
            )

        return "END Invalid input. Please start again."

    # ── MASTER shortcut (simple for USSD; full reg via voice) ─────────────────
    if choice == "2":
        if depth == 1:
            return "CON Enter your full name:"
        if depth == 2:
            return "CON Enter your town or county:"
        if depth == 3:
            return (
                "CON Your main trade:\n"
                "1. Welding  2. Tailoring  3. Plumbing\n"
                "4. Carpentry  5. Hairdressing\n"
                "6. Motorcycle Repair  7. Masonry"
            )
        if depth == 4:
            return "END ✅ Thank you, Master Artisan!\nWe'll contact you when a youth matches your trade.\nJua Kali Matcher 🔧"

    # ── Find existing match ───────────────────────────────────────────────────
    if choice == "3":
        if not youth.trade:
            return "END You are not registered yet.\nDial again and choose option 1."
        try:
            matches = find_matches(phone)
        except Exception as e:
            log.error("Match lookup failed: %s", e)
            return "END Service temporarily unavailable. Please try again."

        if not matches:
            return "END No matches found yet. We'll SMS you when one is available! 🙏"

        lines = [f"END Your Top Matches 🔧\n"]
        for m in matches:
            lines.append(f"{m['rank']}. {m['name']} ({m['trade']}) - {m['location']}")
        return "\n".join(lines)

    return "END Invalid option. Please try again."
