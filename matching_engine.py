"""
matching_engine.py — Dev 1: The Logic Architect
================================================
Semantic matching between employers and job seekers using Gemini embeddings.

- Employer  (user_type="employer")  → matched against job_seekers
- Job Seeker (user_type="job_seeker") → matched against employers
"""
import json, math, logging

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL, MATCH_THRESHOLD, MAX_MATCHES
from database import get_session, Youth, Master, Match

log    = logging.getLogger(__name__)
client = genai.Client(api_key=GEMINI_API_KEY)


# ── Embedding ─────────────────────────────────────────────────────────────────

def _embed(text: str) -> list[float]:
    """MOCK MODE: Return dummy embedding vector"""
    return [0.1] * 768


def _cosine(a: list[float], b: list[float]) -> float:
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    return 0.0 if (mag_a == 0 or mag_b == 0) else dot / (mag_a * mag_b)


# ── Profile text builders ─────────────────────────────────────────────────────

def _caller_profile(caller: Youth) -> str:
    if caller.user_type == "employer":
        return (
            f"I am an employer in {caller.location or 'Kenya'} looking to hire "
            f"a skilled {caller.trade or 'worker'}. "
            f"I need someone with {caller.skill_level or 'any'} level experience. "
            f"Details: {caller.raw_speech or caller.trade}."
        )
    else:
        return (
            f"I am a job seeker from {caller.location or 'Kenya'} "
            f"with skills in {caller.trade or 'general work'}. "
            f"My level is {caller.skill_level or 'beginner'}. "
            f"About me: {caller.raw_speech or caller.trade}."
        )


def _master_profile_text(master: Master) -> str:
    return (
        f"I am a master artisan specialising in {master.trade} "
        f"based in {master.location}. "
        f"I have {master.years_exp} years of experience. "
        f"I offer: {master.bio}."
    )


# ── Embedding cache helpers ───────────────────────────────────────────────────

def _get_caller_embedding(caller: Youth, session) -> list[float]:
    if caller.embedding:
        return json.loads(caller.embedding)
    vec = _embed(_caller_profile(caller))
    caller.embedding = json.dumps(vec)
    session.commit()
    return vec


def _get_master_embedding(master: Master, session) -> list[float]:
    if master.embedding:
        return json.loads(master.embedding)
    vec = _embed(_master_profile_text(master))
    master.embedding = json.dumps(vec)
    session.commit()
    return vec


# ── Main match function ───────────────────────────────────────────────────────

def find_matches(phone: str) -> list[dict]:
    """
    Match a caller (employer or job_seeker) against the opposite pool.

    Employer   → matched against job_seekers in Youth table
    Job seeker → matched against employers in Youth table AND master artisans
    """
    session = get_session()
    try:
        caller = session.query(Youth).filter_by(phone=phone).first()
        if not caller:
            raise ValueError(f"Caller {phone} not in database")

        caller_vec = _get_caller_embedding(caller, session)
        ranked     = []

        if caller.user_type == "employer":
            # Employers see job seekers
            candidates = (
                session.query(Youth)
                .filter(Youth.user_type == "job_seeker")
                .filter(Youth.phone != phone)
                .filter(Youth.trade != None)
                .all()
            )
            for c in candidates:
                vec   = _get_caller_embedding(c, session)
                score = _cosine(caller_vec, vec)
                if score >= MATCH_THRESHOLD:
                    ranked.append({
                        "name":     c.name,
                        "trade":    c.trade,
                        "location": c.location,
                        "phone":    c.phone,
                        "level":    c.skill_level,
                        "score":    score,
                        "type":     "job_seeker",
                    })

        else:
            # Job seekers see employers AND master artisans
            # — other callers who are employers
            employers = (
                session.query(Youth)
                .filter(Youth.user_type == "employer")
                .filter(Youth.trade != None)
                .all()
            )
            for e in employers:
                vec   = _get_caller_embedding(e, session)
                score = _cosine(caller_vec, vec)
                if score >= MATCH_THRESHOLD:
                    ranked.append({
                        "name":     e.name,
                        "trade":    e.trade,
                        "location": e.location,
                        "phone":    e.phone,
                        "level":    "employer",
                        "score":    score,
                        "type":     "employer",
                    })

            # — seeded master artisans
            masters = session.query(Master).filter(Master.capacity > 0).all()
            for m in masters:
                vec   = _get_master_embedding(m, session)
                score = _cosine(caller_vec, vec)
                if score >= MATCH_THRESHOLD:
                    ranked.append({
                        "name":     m.name,
                        "trade":    m.trade,
                        "location": m.location,
                        "phone":    m.phone,
                        "level":    f"{m.years_exp} yrs exp",
                        "score":    score,
                        "type":     "master",
                    })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        top = ranked[:MAX_MATCHES]

        # Persist match records
        for item in top:
            if item["type"] in ("master",):
                m_obj = session.query(Master).filter_by(phone=item["phone"]).first()
                if m_obj:
                    session.add(Match(youth_id=caller.id, master_id=m_obj.id, score=item["score"]))

        session.commit()
        for i, item in enumerate(top):
            item["rank"] = i + 1
        return top

    finally:
        session.close()


def summarise_voice_transcript(transcript: str, user_type: str = "job_seeker") -> dict:
    """Legacy helper kept for USSD path."""
    prompt = f"""
Extract a caller profile from this Kenyan voice transcript.
User type: {user_type}
Transcript: "{transcript}"

Return ONLY valid JSON with: name, location, trade, skill_level.
Use null for missing fields.
"""
    try:
        resp = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        raw  = resp.text.strip().strip("```json").strip("```").strip()
        return json.loads(raw)
    except Exception:
        return {"name": None, "location": None, "trade": None, "skill_level": "beginner"}
