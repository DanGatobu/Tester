# 🔧 Jua Kali Matcher

A voice-first platform that connects Kenyan youth job seekers and employers with master artisans using Africa's Talking (USSD + Voice + SMS) and Google Gemini AI.

---

## What it does

Jua Kali Matcher lets anyone in Kenya — with or without a smartphone — register as a job seeker or employer by simply dialing a USSD code or making a phone call. The system:

1. Captures the caller's profile via USSD menus or a voice recording
2. Uses **Gemini AI** to transcribe the voice recording and extract structured profile data (name, location, trade, skill level)
3. Generates **semantic embeddings** of each profile and runs cosine similarity matching
4. Sends an **SMS to both parties** when a match is found

---

## Architecture

```
Caller dials *384*57799#  ──►  /ussd          (USSD flow)
Caller dials phone number ──►  /voice/answer  (IVR)
                               /voice/ivr     (digit capture)
                               /voice/recording (Gemini STT + match)
                                    │
                               matching_engine.py
                               (Gemini embeddings + cosine similarity)
                                    │
                               sms_handler.py
                               (Africa's Talking SMS to both parties)
```

### Key files

| File | Role |
|---|---|
| `app.py` | Flask server, all routes and live dashboard |
| `ussd_handler.py` | USSD session state machine |
| `voice_handler.py` | IVR flow, Gemini STT, profile extraction |
| `matching_engine.py` | Gemini embeddings + cosine similarity matching |
| `sms_handler.py` | Africa's Talking SMS dispatch |
| `database.py` | SQLAlchemy models: `Youth`, `Master`, `Match` |
| `config.py` | Environment config (API keys, thresholds) |

---

## Tech stack

- **Python / Flask** — web server
- **Africa's Talking** — USSD, Voice IVR, SMS
- **Google Gemini** — speech-to-text (`gemini-2.0-flash`), profile extraction, semantic embeddings (`text-embedding-004`)
- **SQLAlchemy + SQLite** — data persistence
- **Docker / Gunicorn** — containerised deployment (Cloud Run ready)

---

## Getting started

### Prerequisites

- Python 3.11+
- An [Africa's Talking](https://africastalking.com) account (sandbox works for dev)
- A [Google AI Studio](https://aistudio.google.com) API key

### Install

```bash
git clone <repo-url>
cd hath
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configure

Copy `.env` and fill in your keys:

```bash
cp .env .env.local
```

```env
GEMINI_API_KEY=your_gemini_key
AT_USERNAME=sandbox
AT_API_KEY=your_at_api_key
AT_SHORTCODE=*384*57799#
AT_SENDER_ID=JuaKali
SECRET_KEY=your-secret
DATABASE_URL=sqlite:///juakali.db
PORT=5000
DEBUG=true
```

### Run

```bash
python app.py
```

The server starts on `http://localhost:5000`. Open the dashboard at `/`.

To expose it to Africa's Talking webhooks during development, use [ngrok](https://ngrok.com):

```bash
ngrok http 5000
```

Then set your AT callback URLs to:
- USSD: `https://<ngrok-url>/ussd`
- Voice answer: `https://<ngrok-url>/voice/answer`
- Voice recording: `https://<ngrok-url>/voice/recording`

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/ussd` | Africa's Talking USSD callback |
| `POST` | `/voice/answer` | Incoming call answered |
| `POST` | `/voice/ivr` | DTMF digit received |
| `POST` | `/voice/recording` | Recording ready (triggers STT + match) |
| `GET` | `/` or `/dashboard` | Live HTML dashboard |
| `GET` | `/health` | Health check |
| `GET` | `/api/youth` | All registered callers |
| `GET` | `/api/masters` | All master artisans |
| `GET` | `/api/matches` | All matches |
| `POST` | `/api/match/<phone>` | Manually trigger match for a phone number |
| `POST` | `/api/simulate` | Dashboard wizard: simulate a caller without AT |

---

## Dashboard

The live dashboard at `/` shows:

- Real-time counts of callers, employers, job seekers, matches, and SMS sent
- A **Demo Wizard** to simulate a caller without needing a real phone call
- Tables for all callers, master artisans, and matches made

---

## Docker

```bash
docker build -t juakali-matcher .
docker run -p 8080:8080 --env-file .env juakali-matcher
```

The image is Cloud Run compatible — set the `PORT` environment variable and deploy directly.

---

## Matching logic

- Each profile is converted to a text description and embedded using `text-embedding-004`
- Cosine similarity is computed between the caller and all candidates in the opposite pool
- Matches above the `MATCH_THRESHOLD` (default `0.70`) are returned, up to `MAX_MATCHES` (default `3`)
- Employers are matched against job seekers; job seekers are matched against employers and seeded master artisans

---

## License

MIT
