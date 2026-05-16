"""
app.py — Dev 5: The Integrator
================================
Flask server wiring all webhooks together.
Endpoints:
  POST /ussd           ← Africa's Talking USSD callback
  POST /voice/answer   ← AT Voice call answered
  POST /voice/recording← AT Voice recording ready
  GET  /health         ← Health check
  GET  /dashboard      ← Live HTML dashboard
  GET  /api/matches    ← REST: all matches
  GET  /api/youth      ← REST: all youth
  GET  /api/masters    ← REST: all masters
  POST /api/match/<ph> ← REST: manually trigger match for phone
"""
import logging
from flask import Flask, request, jsonify, Response, render_template_string, send_file, send_file

from config import SECRET_KEY, PORT, DEBUG
from database import init_db, get_session, Youth, Master, Match
from ussd_handler import handle_ussd
from voice_handler import voice_answer, voice_ivr, voice_recording
from sms_handler import send_match_sms
from matching_engine import find_matches

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Bootstrap DB ──────────────────────────────────────────────────────────────
with app.app_context():
    init_db()


# ═══════════════════════════════════════════════════════════════════════════════
# USSD
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/ussd", methods=["POST"])
def ussd():
    session_id   = request.form.get("sessionId",   "")
    phone        = request.form.get("phoneNumber",  "")
    text         = request.form.get("text",         "")
    service_code = request.form.get("serviceCode",  "")
    log.info("USSD | session=%s phone=%s text=%r", session_id, phone, text)
    resp = handle_ussd(session_id, phone, text, service_code)
    return Response(resp, mimetype="text/plain")


# ═══════════════════════════════════════════════════════════════════════════════
# VOICE
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/voice/answer", methods=["POST", "GET"])
def voice_answer_route():
    session_id = request.values.get("sessionId", "")
    phone      = request.values.get("callerNumber", "")
    direction  = request.values.get("direction", "Inbound")
    xml = voice_answer(session_id, phone, direction)
    return Response(xml, mimetype="application/xml")


@app.route("/voice/ivr", methods=["POST", "GET"])
def voice_ivr_route():
    """Receives the DTMF digit (1=employer, 2=job seeker) from Africa's Talking."""
    session_id = request.values.get("sessionId", "")
    phone      = request.values.get("callerNumber", "")
    digits     = request.values.get("dtmfDigits", "")
    log.info("IVR digit=%r phone=%s", digits, phone)
    xml = voice_ivr(session_id, phone, digits)
    return Response(xml, mimetype="application/xml")


@app.route("/voice/recording", methods=["POST"])
def voice_recording_route():
    session_id    = request.values.get("sessionId", "")
    phone         = request.values.get("callerNumber", "")
    recording_url = request.values.get("recordingUrl", "")
    duration      = request.values.get("duration", "0")
    xml = voice_recording(session_id, phone, recording_url, duration)
    return Response(xml, mimetype="application/xml")


@app.route("/dummy_audio", methods=["GET"])
def dummy_audio_route():
    return send_file("dummy.wav", mimetype="audio/wav")


# ═══════════════════════════════════════════════════════════════════════════════
# REST API
# ═══════════════════════════════════════════════════════════════════════════════
@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "Jua Kali Matcher"})


@app.route("/api/youth")
def api_youth():
    session = get_session()
    try:
        rows = session.query(Youth).all()
        return jsonify([{
            "id": y.id, "phone": y.phone, "name": y.name,
            "location": y.location, "trade": y.trade,
            "skill_level": y.skill_level, "created_at": str(y.created_at)
        } for y in rows])
    finally:
        session.close()


@app.route("/api/masters")
def api_masters():
    session = get_session()
    try:
        rows = session.query(Master).all()
        return jsonify([{
            "id": m.id, "phone": m.phone, "name": m.name,
            "location": m.location, "trade": m.trade,
            "years_exp": m.years_exp, "capacity": m.capacity
        } for m in rows])
    finally:
        session.close()


@app.route("/api/matches")
def api_matches():
    session = get_session()
    try:
        rows = session.query(Match).all()
        return jsonify([{
            "id": m.id,
            "youth":  m.youth.name  if m.youth  else None,
            "master": m.master.name if m.master else None,
            "score":  m.score,
            "status": m.status,
            "created_at": str(m.created_at)
        } for m in rows])
    finally:
        session.close()


@app.route("/api/match/<phone>", methods=["POST"])
def api_trigger_match(phone):
    try:
        matches = find_matches(phone)
        if matches:
            send_match_sms(phone, matches)
        return jsonify({"matches": matches})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jua Kali Matcher — Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0f;
    --surface: #12121a;
    --card: #1a1a28;
    --border: #2a2a40;
    --accent: #f97316;
    --accent2: #8b5cf6;
    --green: #22c55e;
    --text: #e2e8f0;
    --muted: #64748b;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; min-height: 100vh; }

  header {
    background: linear-gradient(135deg, #1a0a00 0%, #0f0a1a 100%);
    border-bottom: 1px solid var(--border);
    padding: 1.5rem 2rem;
    display: flex; align-items: center; gap: 1rem;
  }
  .logo { font-size: 2rem; }
  .brand h1 { font-size: 1.5rem; font-weight: 900; background: linear-gradient(90deg, var(--accent), var(--accent2)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .brand p { color: var(--muted); font-size: 0.85rem; }

  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; padding: 2rem; }
  .stat-card {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 1.5rem; position: relative; overflow: hidden;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 32px rgba(249,115,22,0.15); }
  .stat-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: linear-gradient(90deg, var(--accent), var(--accent2)); }
  .stat-value { font-size: 2.5rem; font-weight: 900; color: var(--accent); }
  .stat-label { color: var(--muted); font-size: 0.85rem; margin-top: 0.25rem; }
  .stat-icon  { font-size: 1.5rem; position: absolute; top: 1rem; right: 1rem; opacity: 0.3; }

  .section { padding: 0 2rem 2rem; }
  .section-title { font-size: 1.1rem; font-weight: 700; color: var(--text); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
  .section-title span { width: 8px; height: 8px; border-radius: 50%; background: var(--accent); display: inline-block; }

  table { width: 100%; border-collapse: collapse; background: var(--card); border-radius: 12px; overflow: hidden; border: 1px solid var(--border); }
  th { background: var(--surface); padding: 0.75rem 1rem; text-align: left; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
  td { padding: 0.75rem 1rem; border-top: 1px solid var(--border); font-size: 0.875rem; }
  tr:hover td { background: rgba(249,115,22,0.04); }

  .badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 20px; font-size: 0.7rem; font-weight: 600; }
  .badge-trade  { background: rgba(139,92,246,0.2); color: #a78bfa; }
  .badge-level  { background: rgba(34,197,94,0.15); color: #4ade80; }
  .badge-score  { background: rgba(249,115,22,0.2); color: var(--accent); }

  .refresh-btn {
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    color: white; border: none; padding: 0.6rem 1.2rem;
    border-radius: 8px; font-weight: 600; cursor: pointer;
    transition: opacity 0.2s; font-size: 0.85rem;
    margin-left: auto; display: block; text-decoration: none;
  }
  .refresh-btn:hover { opacity: 0.85; }

  /* Wizard Styles */
  .wizard-card {
    background: linear-gradient(to right, rgba(26,26,40,0.8), rgba(26,26,40,0.4));
    border: 1px solid var(--accent); border-radius: 12px;
    padding: 1.5rem; margin: 0 2rem 2rem;
    box-shadow: 0 0 20px rgba(249,115,22,0.1);
  }
  .wizard-card h3 { color: var(--accent); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }
  .form-group { margin-bottom: 1rem; }
  .form-group label { display: block; font-size: 0.85rem; color: var(--muted); margin-bottom: 0.5rem; }
  .form-control { width: 100%; background: var(--surface); border: 1px solid var(--border); color: var(--text); padding: 0.75rem; border-radius: 6px; font-family: inherit; }
  .form-control:focus { outline: none; border-color: var(--accent); }
  .btn-submit { background: var(--accent); color: white; border: none; padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: 600; cursor: pointer; transition: 0.2s; }
  .btn-submit:hover { background: #ea580c; }


  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--green); display: inline-block; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }

  .empty { text-align: center; color: var(--muted); padding: 2rem; }
</style>
</head>
<body>
<header>
  <div class="logo">🔧</div>
  <div class="brand">
    <h1>Jua Kali Apprenticeship Matcher</h1>
    <p><span class="live-dot"></span> Live Dashboard &nbsp;·&nbsp; Africa's Talking + Gemini AI</p>
  </div>
  <button class="refresh-btn" onclick="location.reload()">↻ Refresh</button>
  </header>

<div class="wizard-card">
  <h3>✨ Live Demo Wizard: Simulate a Caller</h3>
  <form id="wizard-form" onsubmit="submitWizard(event)">
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
      <div class="form-group">
        <label>1. Who is calling?</label>
        <select id="userType" class="form-control" required>
          <option value="employer">1 — Hiring (Employer)</option>
          <option value="job_seeker">2 — Looking for work (Job Seeker)</option>
        </select>
      </div>
      <div class="form-group">
        <label>2. Phone Number</label>
        <input type="text" id="phone" class="form-control" placeholder="+254700000000" value="+254799888777" required>
      </div>
    </div>
    <div class="form-group">
      <label>3. Voice Message Transcript (What did they say?)</label>
      <input type="text" id="transcript" class="form-control" placeholder="e.g. My name is John, I live in Nairobi and I need an experienced welder..." required>
    </div>
    <button type="submit" id="submitBtn" class="btn-submit">Simulate Call & Match!</button>
  </form>
</div>

<div class="stats">
  <div class="stat-card">
    <div class="stat-icon">📞</div>
    <div class="stat-value" id="youth-count">{{youth_count}}</div>
    <div class="stat-label">Total Callers</div>
  </div>
  <div class="stat-card">
    <div class="stat-icon">💼</div>
    <div class="stat-value">{{employer_count}}</div>
    <div class="stat-label">Hiring (Employers)</div>
  </div>
  <div class="stat-card">
    <div class="stat-icon">👷</div>
    <div class="stat-value">{{seeker_count}}</div>
    <div class="stat-label">Job Seekers</div>
  </div>
  <div class="stat-card">
    <div class="stat-icon">🤝</div>
    <div class="stat-value" id="match-count">{{match_count}}</div>
    <div class="stat-label">Matches Made</div>
  </div>
  <div class="stat-card">
    <div class="stat-icon">📱</div>
    <div class="stat-value" id="sms-count">{{sms_count}}</div>
    <div class="stat-label">SMS Sent</div>
  </div>
</div>

<div class="section">
  <div class="section-title"><span></span>Callers — Live Register</div>
  <table>
    <thead><tr><th>Name</th><th>Phone</th><th>Role</th><th>Location</th><th>Trade / Skill</th><th>Level</th><th>Called</th></tr></thead>
    <tbody>
    {% for y in youth %}
    <tr>
      <td>{{ y.name or '—' }}</td>
      <td>{{ y.phone }}</td>
      <td>
        {% if y.user_type == 'employer' %}
          <span class="badge" style="background:rgba(249,115,22,0.2);color:#fb923c">💼 Hiring</span>
        {% else %}
          <span class="badge" style="background:rgba(34,197,94,0.15);color:#4ade80">👷 Job Seeker</span>
        {% endif %}
      </td>
      <td>{{ y.location or '—' }}</td>
      <td><span class="badge badge-trade">{{ y.trade or '—' }}</span></td>
      <td><span class="badge badge-level">{{ y.skill_level or '—' }}</span></td>
      <td>{{ y.created_at.strftime('%d %b %H:%M') if y.created_at else '—' }}</td>
    </tr>
    {% else %}
    <tr><td colspan="7" class="empty">No calls yet — waiting for first caller 📞</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title"><span></span>Master Artisans</div>
  <table>
    <thead><tr><th>Name</th><th>Phone</th><th>Location</th><th>Trade</th><th>Experience</th><th>Open Slots</th></tr></thead>
    <tbody>
    {% for m in masters %}
    <tr>
      <td>{{ m.name }}</td>
      <td>{{ m.phone }}</td>
      <td>{{ m.location }}</td>
      <td><span class="badge badge-trade">{{ m.trade }}</span></td>
      <td>{{ m.years_exp }} yrs</td>
      <td><span class="badge badge-level">{{ m.capacity }}</span></td>
    </tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<div class="section">
  <div class="section-title"><span></span>Matches Made</div>
  <table>
    <thead><tr><th>Youth</th><th>Master</th><th>Score</th><th>Status</th><th>When</th></tr></thead>
    <tbody>
    {% for m in matches %}
    <tr>
      <td>{{ m.youth.name  if m.youth  else '—' }}</td>
      <td>{{ m.master.name if m.master else '—' }}</td>
      <td><span class="badge badge-score">{{ "%.0f%%"|format(m.score * 100) }}</span></td>
      <td>{{ m.status }}</td>
      <td>{{ m.created_at.strftime('%d %b %H:%M') if m.created_at else '—' }}</td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="empty">No matches yet — register a youth to see the magic! ✨</td></tr>
    {% endfor %}
    </tbody>
  </table>
</div>

<script>
  // Auto-refresh every 30 seconds
  let timer = setTimeout(() => location.reload(), 30000);

  async function submitWizard(e) {
    e.preventDefault();
    clearTimeout(timer);
    const btn = document.getElementById('submitBtn');
    btn.innerText = "Simulating... Please wait";
    btn.style.opacity = "0.7";

    const payload = {
      phone: document.getElementById('phone').value,
      user_type: document.getElementById('userType').value,
      transcript: document.getElementById('transcript').value
    };

    try {
      const res = await fetch('/api/simulate', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        location.reload(); // Refresh immediately to show the new match
      } else {
        alert("Simulation failed. Check logs.");
        btn.innerText = "Simulate Call & Match!";
        btn.style.opacity = "1";
      }
    } catch (err) {
      alert("Error: " + err);
    }
  }
</script>
</body>
</html>
"""

@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Endpoint for the Web UI Wizard to bypass AT completely."""
    data = request.json
    phone = data.get("phone")
    user_type = data.get("user_type")
    transcript = data.get("transcript")

    # MOCK PROFILE EXTRACTION based on input text
    # In a real app this would hit Gemini STT/Extraction, but we'll mock it based on inputs
    import random
    profile = {
        "name": "Wizard Caller",
        "location": "Nairobi",
        "trade": "welding" if "weld" in transcript.lower() else "tailoring" if "tailor" in transcript.lower() else "plumbing",
        "skill_level": "experienced",
        "job_details": transcript
    }

    session = get_session()
    try:
        caller = session.query(Youth).filter_by(phone=phone).first()
        if not caller:
            caller = Youth(phone=phone)
            session.add(caller)
        caller.name        = profile["name"]
        caller.location    = profile["location"]
        caller.trade       = profile["trade"]
        caller.skill_level = profile["skill_level"]
        caller.user_type   = user_type
        caller.raw_speech  = transcript
        session.commit()
    finally:
        session.close()

    try:
        from matching_engine import find_matches
        find_matches(phone) # Will create the match in the DB
    except Exception as e:
        log.error("Wizard Match Error: %s", e)

    return jsonify({"status": "success", "profile": profile})


@app.route("/dashboard")
@app.route("/")
def dashboard():
    session = get_session()
    try:
        youth   = session.query(Youth).order_by(Youth.created_at.desc()).limit(20).all()
        masters = session.query(Master).all()
        matches = session.query(Match).order_by(Match.created_at.desc()).limit(20).all()
        return render_template_string(
            DASHBOARD_HTML,
            youth=youth,
            masters=masters,
            matches=matches,
            youth_count=session.query(Youth).count(),
            master_count=session.query(Master).count(),
            match_count=session.query(Match).count(),
            employer_count=session.query(Youth).filter_by(user_type="employer").count(),
            seeker_count=session.query(Youth).filter_by(user_type="job_seeker").count(),
            sms_count=session.query(Match).count() * 2,
        )
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
