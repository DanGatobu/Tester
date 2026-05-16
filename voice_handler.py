"""
voice_handler.py — Dev 3: The Voice Lead (IVR Edition)
========================================================
Call flow:
  1. /voice/answer   → "Press 1 if hiring | Press 2 if looking for work"
  2. /voice/ivr      → stores caller type → "After the tone, say your name,
                        location and describe the job..."
  3. /voice/recording → Gemini STT → extract profile → match → SMS both parties
"""
import logging, tempfile, os, requests, json

from google import genai
from database import get_session, Youth
from config import GEMINI_API_KEY, GEMINI_MODEL

log    = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Answer: Play IVR menu, capture digit
# ═══════════════════════════════════════════════════════════════════════════════

def voice_answer(session_id: str, phone: str, direction: str) -> str:
    """
    Called when someone dials the number.
    Returns AT Voice XML with GetDigits to differentiate employer vs job seeker.
    """
    log.info("📞 Incoming call — session=%s  phone=%s", session_id, phone)
    return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <GetDigits timeout="15" finishOnKey="#" callbackUrl="/voice/ivr">
    <Say voice="en-US">
      Welcome to Jua Kali Matcher. Kenya's fastest way to connect artisans
      with opportunities.
      Press 1 if you are hiring or looking for a skilled worker.
      Press 2 if you are looking for a job or apprenticeship.
      Then press the hash key.
    </Say>
  </GetDigits>
  <Say>We did not receive your selection. Please call back and try again. Goodbye.</Say>
</Response>"""


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — IVR: digit received → store type → prompt for voice message
# ═══════════════════════════════════════════════════════════════════════════════

def voice_ivr(session_id: str, phone: str, digits: str) -> str:
    """
    Called after user presses 1 or 2.
    Saves user_type to DB, then returns Record XML with role-appropriate prompt.
    """
    digit = (digits or "").strip()
    log.info("📲 IVR digit=%r  phone=%s", digit, phone)

    if digit == "1":
        user_type = "employer"
        prompt = (
            "You pressed 1. Great! We will now record your hiring request. "
            "After the beep, please say: "
            "Your name. "
            "Your location or area. "
            "The type of worker or skill you need. "
            "And any important details like hours or pay. "
            "You have up to sixty seconds. Speak after the beep."
        )
    elif digit == "2":
        user_type = "job_seeker"
        prompt = (
            "You pressed 2. Great! We will now record your profile. "
            "After the beep, please say: "
            "Your name. "
            "Your location or area. "
            "The type of work or trade you do or want to learn. "
            "And any skills or experience you have. "
            "You have up to sixty seconds. Speak after the beep."
        )
    else:
        return """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Invalid selection. Please call back and press 1 or 2. Goodbye.</Say>
</Response>"""

    # ── Save user_type into DB now so recording callback can retrieve it ───────
    session = get_session()
    try:
        caller = session.query(Youth).filter_by(phone=phone).first()
        if not caller:
            caller = Youth(phone=phone)
            session.add(caller)
        caller.user_type = user_type
        session.commit()
    finally:
        session.close()

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="en-US">{prompt}</Say>
  <Record
    finishOnKey="#"
    maxLength="60"
    trimSilence="true"
    playBeep="true"
    callbackUrl="/voice/recording"
  />
</Response>"""


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Recording: STT → extract profile → match → SMS
# ═══════════════════════════════════════════════════════════════════════════════

def voice_recording(session_id: str, phone: str, recording_url: str, duration: str) -> str:
    """
    Called when AT has the audio ready.
    Downloads → transcribes → extracts profile → matches → notifies.
    """
    log.info("🎙️  Recording ready — url=%s  duration=%ss", recording_url, duration)

    # ── 1. Retrieve the user_type we saved in step 2 ─────────────────────────
    session = get_session()
    try:
        caller    = session.query(Youth).filter_by(phone=phone).first()
        user_type = caller.user_type if caller else "job_seeker"
    finally:
        session.close()

    # ── 2. Download audio ─────────────────────────────────────────────────────
    audio = _download(recording_url)
    if not audio:
        return _say("Sorry, we could not process your recording. Please call again.")

    # ── 3. Transcribe with Gemini ─────────────────────────────────────────────
    transcript = _transcribe(audio)
    log.info("📝 Transcript: %s", transcript)
    if not transcript:
        return _say("We could not understand your recording. Please call again and speak clearly.")

    # ── 4. Extract structured profile ─────────────────────────────────────────
    profile = _extract_profile(transcript, user_type)
    log.info("🗂️  Profile: %s", profile)

    # ── 5. Save full profile to DB ────────────────────────────────────────────
    session = get_session()
    try:
        caller = session.query(Youth).filter_by(phone=phone).first()
        if not caller:
            caller = Youth(phone=phone)
            session.add(caller)
        caller.name        = profile.get("name")        or caller.name
        caller.location    = profile.get("location")    or caller.location
        caller.trade       = profile.get("trade")       or caller.trade
        caller.skill_level = profile.get("skill_level") or "beginner"
        caller.user_type   = user_type
        caller.raw_speech  = transcript
        session.commit()
    finally:
        session.close()

    # ── 6. Run matching & send SMS ────────────────────────────────────────────
    try:
        from matching_engine import find_matches
        from sms_handler import send_match_sms
        matches = find_matches(phone)
        if matches:
            send_match_sms(phone, matches, user_type)
            name = profile.get("name") or "there"
            return _say(
                f"Thank you {name}! We found {len(matches)} match"
                f"{'es' if len(matches) > 1 else ''} for you. "
                "Check your SMS for the details. Good luck! Goodbye."
            )
        else:
            name = profile.get("name") or "there"
            return _say(
                f"Thank you {name}! Your profile is saved. "
                "We will send you an SMS as soon as we find a match. Goodbye."
            )
    except Exception as e:
        log.error("Match/SMS error: %s", e)
        return _say("Your profile is saved. We will contact you soon. Goodbye.")


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _download(url: str) -> bytes | None:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
        r.raise_for_status()
        return r.content
    except Exception as e:
        log.error("Audio download failed: %s", e)
        return None


def transcribe_audio_file(path: str, mime: str = "audio/wav") -> str:
    """Transcribe an audio file already on disk via Gemini STT."""
    try:
        uploaded = client.files.upload(file=path, config={"mime_type": mime})
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                "Transcribe this audio exactly as spoken by the caller. Output only the transcript text.",
                uploaded,
            ],
        )
        return response.text.strip()
    except Exception as e:
        log.error("Gemini STT error: %s", e)
        return ""


def _transcribe(audio_bytes: bytes) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            path = f.name
        text = transcribe_audio_file(path, "audio/wav")
        os.unlink(path)
        return text
    except Exception as e:
        log.error("Gemini STT error: %s", e)
        return ""


def extract_profile(transcript: str, user_type: str) -> dict:
    """Public wrapper around the Gemini profile extractor."""
    return _extract_profile(transcript, user_type)

def _extract_profile(transcript: str, user_type: str) -> dict:
    """Use Gemini to pull structured fields from free-form voice transcript."""
    if user_type == "employer":
        fields = """
- name       (employer's name — string)
- location   (Kenyan town/area — string)
- trade      (skill/trade needed, e.g. welding, tailoring — string)
- job_details (brief description of the role, hours, pay — string)
- skill_level (required level: any | experienced | expert — string)
"""
    else:
        fields = """
- name       (caller's name — string)
- location   (Kenyan town/area — string)
- trade      (skill/trade they do or want to learn, e.g. welding, tailoring — string)
- skill_level (their level: beginner | intermediate | experienced — string)
- job_details (any extra info they mentioned — string)
"""

    prompt = f"""
You are extracting a caller profile from a Kenyan voice recording transcript.
User type: {user_type}

Transcript: "{transcript}"

Extract and return ONLY valid JSON with these fields:
{fields}
If a field is unclear or not mentioned, use null.
Return ONLY the JSON object, nothing else. No markdown, no backticks.
"""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        raw = response.text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception as e:
        log.error("Profile extraction failed: %s", e)
        return {"name": None, "location": None, "trade": None,
                "skill_level": "beginner", "job_details": None}


def _say(message: str) -> str:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Say voice="en-US">{message}</Say></Response>'
    )
