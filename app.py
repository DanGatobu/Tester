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
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); padding: 0.75rem 1.25rem; border-radius: 6px; font-weight: 600; cursor: pointer; }
  .btn-ghost:hover { color: var(--text); border-color: var(--muted); }

  /* Wizard steps */
  .wiz-step { display: none; animation: fade 0.25s ease; }
  .wiz-step.active { display: block; }
  @keyframes fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .wiz-progress { display: flex; gap: 0.5rem; margin-bottom: 1.25rem; }
  .wiz-progress div { flex: 1; height: 4px; border-radius: 2px; background: var(--border); transition: 0.3s; }
  .wiz-progress div.on { background: linear-gradient(90deg, var(--accent), var(--accent2)); }
  .choice-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  .choice {
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.5rem; cursor: pointer; text-align: center; transition: 0.2s;
  }
  .choice:hover { border-color: var(--accent); transform: translateY(-3px); box-shadow: 0 8px 24px rgba(249,115,22,0.15); }
  .choice .ico { font-size: 2.5rem; }
  .choice .ttl { font-weight: 700; margin-top: 0.5rem; font-size: 1.05rem; }
  .choice .sub { color: var(--muted); font-size: 0.8rem; margin-top: 0.25rem; }
  .wiz-actions { display: flex; gap: 0.75rem; margin-top: 1.25rem; align-items: center; }
  .hint { font-size: 0.78rem; color: var(--muted); margin-top: 0.4rem; }
  .or-divider { text-align: center; color: var(--muted); font-size: 0.75rem; margin: 0.75rem 0; letter-spacing: 0.1em; }
  .result-box {
    margin-top: 1.25rem; padding: 1rem 1.25rem; border-radius: 10px;
    background: var(--surface); border: 1px solid var(--border); display: none;
  }
  .result-box.show { display: block; }
  .result-box h4 { color: var(--accent); margin-bottom: 0.5rem; }
  .kv { display: flex; gap: 0.5rem; font-size: 0.85rem; padding: 0.2rem 0; }
  .kv b { color: var(--muted); min-width: 110px; display: inline-block; }
  .pill-ok  { display:inline-block; padding:0.2rem 0.6rem; border-radius:20px; font-size:0.72rem; background:rgba(34,197,94,0.15); color:#4ade80; }
  .pill-no  { display:inline-block; padding:0.2rem 0.6rem; border-radius:20px; font-size:0.72rem; background:rgba(148,163,184,0.15); color:#94a3b8; }


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
  <div class="wiz-progress">
    <div id="p1" class="on"></div><div id="p2"></div><div id="p3"></div>
  </div>

  <!-- STEP 1 — choose role -->
  <div class="wiz-step active" id="step1">
    <label style="display:block;color:var(--muted);font-size:0.85rem;margin-bottom:0.75rem;">Step 1 — Who are you?</label>
    <div class="choice-grid">
      <div class="choice" onclick="pickRole('employer')">
        <div class="ico">💼</div>
        <div class="ttl">I'm Hiring</div>
        <div class="sub">Employer / need a worker</div>
      </div>
      <div class="choice" onclick="pickRole('job_seeker')">
        <div class="ico">👷</div>
        <div class="ttl">Looking for a Job</div>
        <div class="sub">Job seeker / apprentice</div>
      </div>
    </div>
  </div>

  <!-- STEP 2 — describe (text or audio) -->
  <div class="wiz-step" id="step2">
    <label style="display:block;color:var(--muted);font-size:0.85rem;margin-bottom:0.5rem;">
      Step 2 — Tell us about <span id="roleWord">it</span>. Our AI extracts your <b>name</b> and the <b>job/skill</b> automatically.
    </label>
    <div class="form-group">
      <textarea id="transcript" class="form-control" rows="3"
        placeholder="e.g. My name is John, I'm in Nairobi and I need an experienced welder for metal gates..."></textarea>
    </div>
    <div class="or-divider">— OR UPLOAD A VOICE NOTE —</div>
    <div class="form-group">
      <input type="file" id="audio" class="form-control" accept="audio/*">
      <div class="hint">🎙️ Upload an audio recording — the AI will transcribe & extract the details.</div>
    </div>
    <div class="wiz-actions">
      <button class="btn-ghost" onclick="goStep(1)">← Back</button>
      <button class="btn-submit" onclick="toStep3()">Next →</button>
    </div>
  </div>

  <!-- STEP 3 — notification number -->
  <div class="wiz-step" id="step3">
    <label style="display:block;color:var(--muted);font-size:0.85rem;margin-bottom:0.5rem;">
      Step 3 — Which number should we SMS when we find a match?
    </label>
    <div class="form-group">
      <input type="text" id="notify_phone" class="form-control"
        placeholder="+2547XXXXXXXX" value="+254799888777">
      <div class="hint">📱 If a match is found, an SMS notification is sent to this number.</div>
    </div>
    <div class="wiz-actions">
      <button class="btn-ghost" onclick="goStep(2)">← Back</button>
      <button class="btn-submit" id="submitBtn" onclick="submitWizard()">🔍 Find My Match</button>
    </div>
  </div>

  <div class="result-box" id="resultBox"></div>
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
{% raw %}
  // Auto-refresh every 45 seconds (paused while using the wizard)
  let timer = setTimeout(() => location.reload(), 45000);
  let wiz = { user_type: null };

  function goStep(n) {
    clearTimeout(timer);
    for (let i = 1; i <= 3; i++) {
      document.getElementById('step' + i).classList.toggle('active', i === n);
      document.getElementById('p' + i).classList.toggle('on', i <= n);
    }
  }

  function pickRole(role) {
    wiz.user_type = role;
    document.getElementById('roleWord').innerText =
      role === 'employer' ? 'the worker you need' : 'the work you do';
    goStep(2);
  }

  function toStep3() {
    const txt = document.getElementById('transcript').value.trim();
    const file = document.getElementById('audio').files[0];
    if (!txt && !file) {
      alert('Please type a description or upload an audio note.');
      return;
    }
    goStep(3);
  }

  async function submitWizard() {
    clearTimeout(timer);
    const btn = document.getElementById('submitBtn');
    btn.innerText = '🤖 AI is working...';
    btn.style.opacity = '0.7';

    const fd = new FormData();
    fd.append('user_type', wiz.user_type);
    fd.append('transcript', document.getElementById('transcript').value);
    fd.append('notify_phone', document.getElementById('notify_phone').value);
    const file = document.getElementById('audio').files[0];
    if (file) fd.append('audio', file);

    try {
      const res = await fetch('/api/simulate', { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Simulation failed');

      const p = data.profile || {};
      const m = data.matches || [];
      const box = document.getElementById('resultBox');
      let html = '<h4>🤖 AI Extracted Profile</h4>'
        + '<div class="kv"><b>Name</b><span>' + (p.name || '—') + '</span></div>'
        + '<div class="kv"><b>Job / Skill</b><span>' + (p.trade || '—') + '</span></div>'
        + '<div class="kv"><b>Location</b><span>' + (p.location || '—') + '</span></div>'
        + '<div class="kv"><b>Level</b><span>' + (p.skill_level || '—') + '</span></div>';
      if (m.length) {
        const t = m[0];
        html += '<h4 style="margin-top:1rem">✅ Match Found (' + m.length + ')</h4>'
          + '<div class="kv"><b>Matched With</b><span>' + (t.name || '—') + ' · ' + (t.trade || '—') + '</span></div>'
          + '<div class="kv"><b>Score</b><span>' + Math.round((t.score || 0) * 100) + '%</span></div>'
          + '<div class="kv"><b>SMS to ' + (data.notify_phone || '') + '</b><span class="'
          + (data.sms_sent ? 'pill-ok">Sent ✓' : 'pill-no">Queued (sandbox)') + '</span></div>';
      } else {
        html += '<h4 style="margin-top:1rem">🔎 No match yet</h4>'
          + '<div class="hint">Saved to the register. Add a counterpart and try again to see a live match.</div>';
      }
      html += '<div class="wiz-actions"><button class="btn-submit" onclick="location.reload()">Done — Refresh Dashboard</button></div>';
      box.innerHTML = html;
      box.classList.add('show');
      document.querySelectorAll('.wiz-step').forEach(s => s.classList.remove('active'));
    } catch (err) {
      alert('Error: ' + err.message);
      btn.innerText = '🔍 Find My Match';
      btn.style.opacity = '1';
    }
  }
{% endraw %}
</script>
</body>
</html>
"""

def _keyword_profile(transcript: str, user_type: str) -> dict:
    """Offline parser used when Gemini is unavailable — extracts name,
    trade, location and level so the demo stays convincing."""
    import re
    text = transcript or ""
    t    = text.lower()

    # ── Name ──────────────────────────────────────────────────────────────
    name = None
    for pat in (r"my name is ([a-z]+(?:\s[a-z]+)?)",
                r"i am ([a-z]+(?:\s[a-z]+)?)",
                r"i'm ([a-z]+(?:\s[a-z]+)?)",
                r"this is ([a-z]+(?:\s[a-z]+)?)",
                r"called ([a-z]+(?:\s[a-z]+)?)"):
        m = re.search(pat, t)
        if m:
            cand = m.group(1).strip()
            if cand not in ("a", "an", "the", "looking", "in", "from"):
                name = cand.title()
                break

    # ── Trade / skill ─────────────────────────────────────────────────────
    trade = ("welding" if "weld" in t else
             "tailoring" if "tailor" in t or "sew" in t or "dressmak" in t else
             "plumbing" if "plumb" in t else
             "carpentry" if "carpent" in t or "wood" in t or "furniture" in t else
             "electrical" if "electric" in t or "wiring" in t else
             "mechanic" if "mechanic" in t or "garage" in t or "motor" in t else
             "masonry" if "mason" in t or "build" in t or "construct" in t else
             "painting" if "paint" in t else
             "general")

    # ── Location ──────────────────────────────────────────────────────────
    towns = ["nairobi", "mombasa", "kisumu", "nakuru", "eldoret", "thika",
             "machakos", "nyeri", "kakamega", "kitale", "garissa", "meru",
             "kericho", "embu", "kiambu", "ruiru", "kisii", "malindi"]
    location = next((c.title() for c in towns if c in t), "Nairobi")

    # ── Level ─────────────────────────────────────────────────────────────
    level = ("expert" if "expert" in t or "master" in t else
             "experienced" if "experience" in t or "skilled" in t or "years" in t else
             "beginner" if "beginner" in t or "learn" in t or "apprentice" in t else
             "intermediate")

    return {"name": name or "Wizard Caller", "location": location,
            "trade": trade, "skill_level": level, "job_details": text}


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    """Web wizard: role → describe (text or audio) → notify number.
    AI extracts the name + job/skill; on a match an SMS is sent."""
    import random, tempfile, os

    user_type    = (request.form.get("user_type") or "job_seeker").strip()
    transcript   = (request.form.get("transcript") or "").strip()
    notify_phone = (request.form.get("notify_phone") or "").strip()
    audio        = request.files.get("audio")

    # ── 1. If an audio note was uploaded, transcribe it with Gemini ───────────
    if audio and audio.filename:
        try:
            ext  = os.path.splitext(audio.filename)[1] or ".wav"
            mime = audio.mimetype or "audio/wav"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                audio.save(f.name)
                tmp = f.name
            from voice_handler import transcribe_audio_file
            spoken = transcribe_audio_file(tmp, mime)
            os.unlink(tmp)
            if spoken:
                transcript = (transcript + " " + spoken).strip()
        except Exception as e:
            log.error("Wizard audio transcription failed: %s", e)

    if not transcript:
        return jsonify({"error": "No description or audio provided"}), 400

    # ── 2. AI extracts name + job/skill (Gemini, with safe fallback) ──────────
    try:
        from voice_handler import extract_profile
        profile = extract_profile(transcript, user_type) or {}
        if not profile.get("trade") and not profile.get("name"):
            profile = _keyword_profile(transcript, user_type)
    except Exception as e:
        log.error("Wizard extraction failed, using fallback: %s", e)
        profile = _keyword_profile(transcript, user_type)

    profile.setdefault("name", "Wizard Caller")
    profile.setdefault("location", "Nairobi")
    profile.setdefault("trade", "general")
    profile.setdefault("skill_level", "experienced")

    # ── 3. Persist the simulated caller (unique phone per simulation) ─────────
    sim_phone = "+254" + "".join(str(random.randint(0, 9)) for _ in range(9))
    session = get_session()
    try:
        caller = Youth(phone=sim_phone)
        session.add(caller)
        caller.name         = profile.get("name")
        caller.location     = profile.get("location")
        caller.trade        = profile.get("trade")
        caller.skill_level  = profile.get("skill_level")
        caller.user_type    = user_type
        caller.notify_phone = notify_phone or None
        caller.raw_speech   = transcript
        session.commit()
    finally:
        session.close()

    # ── 4. Match, and SMS the notify number if a match is found ──────────────
    matches  = []
    sms_sent = False
    try:
        from matching_engine import find_matches
        matches = find_matches(sim_phone)
        if matches and notify_phone:
            from sms_handler import send_match_notification
            sms_sent = send_match_notification(
                notify_phone, profile, matches, user_type)
    except Exception as e:
        log.error("Wizard match/SMS error: %s", e)

    return jsonify({
        "status": "success",
        "profile": profile,
        "matches": matches,
        "notify_phone": notify_phone,
        "sms_sent": sms_sent,
    })


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
