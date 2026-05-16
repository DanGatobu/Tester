import os
from dotenv import load_dotenv

load_dotenv()

# ── Google / Gemini ───────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAPZN_VDEXnPKzLc0_oF5nF06kPH7nMybw")
GEMINI_MODEL   = "gemini-2.0-flash"

# ── Africa's Talking ──────────────────────────────────────────────────────────
AT_USERNAME    = os.getenv("AT_USERNAME", "sandbox")
AT_API_KEY     = os.getenv("AT_API_KEY", "atsk_xxxxxxxxxxxxxxxxxxxxxx")
AT_SHORTCODE   = os.getenv("AT_SHORTCODE", "*384*57799#")   # USSD
AT_SENDER_ID   = os.getenv("AT_SENDER_ID", "JuaKali")       # SMS

# ── App ───────────────────────────────────────────────────────────────────────
SECRET_KEY     = os.getenv("SECRET_KEY", "jua-kali-hackathon-secret")
DATABASE_URL   = os.getenv("DATABASE_URL", "sqlite:///juakali.db")
PORT           = int(os.getenv("PORT", 5000))
DEBUG          = os.getenv("DEBUG", "true").lower() == "true"

# ── Matching ──────────────────────────────────────────────────────────────────
MATCH_THRESHOLD = 0.70   # cosine similarity floor
MAX_MATCHES     = 3      # max masters returned per youth
