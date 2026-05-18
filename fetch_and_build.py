#!/usr/bin/env python3
"""
🚴 David Moreno — Daily Cycling Dashboard Builder
- Fetches wellness (has ctl, atl, tsb, restingHR, hrv, sleepSecs etc.)
- Fetches activities (has icu_training_load, weighted_average_watts, etc.)
- Generates index.html → committed back to repo → served via GitHub Pages
"""

import os
import json
import requests
from datetime import datetime, timedelta

API_KEY  = os.environ["INTERVALS_API_KEY"]
AUTH     = ("API_KEY", API_KEY)
BASE_URL = "https://intervals.icu/api/v1/athlete/0"

ATHLETE = {
    "name":      "David Moreno",
    "team":      "Capos Team",
    "age":       38,
    "weight_kg": 79,
    "height_m":  1.85,
}

def date_str(days_back=0):
    return (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

def get(path, params=None):
    url = f"{BASE_URL}{path}"
    print(f"   GET {url} params={params}")
    r = requests.get(url, auth=AUTH, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# ── FETCH ──────────────────────────────────────────────────
def fetch_all():
    print("📡 Fetching wellness (60 days)...")
    # wellness contains ctl, atl, tsb per day — this is the fitness series!
    wellness = get("/wellness", {
        "oldest": date_str(60),
        "newest": date_str(0),
    })

    print("📡 Fetching activities (60 days)...")
    activities = get("/activities", {
        "oldest": date_str(60) + "T00:00:00",
        "newest": date_str(0)  + "T23:59:59",
    })

    print(f"   Wellness records : {len(wellness)}")
    print(f"   Activities found : {len(activities)}")
    return wellness, activities

# ── COMPUTE SUMMARY ────────────────────────────────────────
def compute_summary(wellness, activities):
    # Latest wellness record has today's CTL/ATL/TSB + all biometrics
    lat = wellness[-1] if wellness else {}

    ctl = lat.get("ctl")
    atl = lat.get("atl")
    tsb = (ctl - atl) if (ctl is not None and atl is not None) else None

    if tsb is None:
        status, status_label = "ready", "🟢 READY TO TRAIN"
    elif tsb < -20:
        status, status_label = "rest",    "🔴 REST DAY"
    elif tsb < -5:
        status, status_label = "caution", "🟡 TAKE IT EASY"
    else:
        status, status_label = "ready",   "🟢 READY TO TRAIN"

    sleep_hrs = round(lat["sleepSecs"] / 3600, 1) if lat.get("sleepSecs") else None

    # Recent activities for brief
    act_lines = []
    for a in reversed(activities[-7:]):
        d    = (a.get("start_date_local") or "")[:10]
        dist = f"{a['distance']/1000:.1f}km"              if a.get("distance")               else ""
        tss  = f"TSS:{round(a['icu_training_load'])}"     if a.get("icu_training_load")       else ""
        np   = f"NP:{round(a['weighted_average_watts'])}w" if a.get("weighted_average_watts") else ""
        hr   = f"HR:{round(a['average_heartrate'])}"      if a.get("average_heartrate")       else ""
        act_lines.append(f"  • {d} — {a.get('name','Ride')} {dist} {tss} {np} {hr}".strip())

    brief = f"""📋 DAILY TRAINING DATA — {datetime.utcnow().strftime('%A, %d %B %Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 ATHLETE: {ATHLETE['name']} | {ATHLETE['age']}y | {ATHLETE['weight_kg']}kg | {ATHLETE['height_m']}m | {ATHLETE['team']}

📊 PERFORMANCE MANAGEMENT:
  • CTL (Fitness):   {round(ctl, 1) if ctl is not None else 'N/A'}
  • ATL (Fatigue):   {round(atl, 1) if atl is not None else 'N/A'}
  • TSB (Form):      {round(tsb, 1) if tsb is not None else 'N/A'}

😴 WELLNESS (LATEST):
  • Resting HR:      {f"{round(lat['restingHR'])} bpm"    if lat.get('restingHR')    else 'N/A'}
  • HRV:             {f"{round(lat['hrv'])} ms"           if lat.get('hrv')           else 'N/A'}
  • Sleep:           {f"{sleep_hrs} hrs"                  if sleep_hrs               else 'N/A'}
  • Sleep quality:   {f"{lat['sleepQuality']}/5"          if lat.get('sleepQuality')  else 'N/A'}
  • Sleep score:     {f"{round(lat['sleepScore'])}/100"   if lat.get('sleepScore')    else 'N/A'}
  • Readiness:       {f"{round(lat['readiness'])}/100"    if lat.get('readiness')     else 'N/A'}
  • Fatigue:         {f"{lat['fatigue']}/7"               if lat.get('fatigue')       else 'N/A'}
  • Soreness:        {f"{lat['soreness']}/7"              if lat.get('soreness')      else 'N/A'}
  • SpO2:            {f"{lat['spO2']}%"                   if lat.get('spO2')          else 'N/A'}

🚴 LAST 7 ACTIVITIES:
{chr(10).join(act_lines) if act_lines else '  No recent activities'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Paste into Claude.ai and ask:
"Analyse my training and give me today's coaching plan"
"""

    return {
        "ctl":           round(ctl, 1)          if ctl is not None      else None,
        "atl":           round(atl, 1)          if atl is not None      else None,
        "tsb":           round(tsb, 1)          if tsb is not None      else None,
        "status":        status,
        "status_label":  status_label,
        "resting_hr":    round(lat["restingHR"])          if lat.get("restingHR")    else None,
        "hrv":           round(lat["hrv"])                if lat.get("hrv")          else None,
        "sleep_hrs":     sleep_hrs,
        "sleep_score":   round(lat["sleepScore"])         if lat.get("sleepScore")   else None,
        "readiness":     round(lat["readiness"])          if lat.get("readiness")    else None,
        "sleep_quality": lat.get("sleepQuality"),
        "fatigue":       lat.get("fatigue"),
        "soreness":      lat.get("soreness"),
        "spo2":          lat.get("spO2"),
        "brief":         brief,
        "updated":       datetime.utcnow().strftime("%A %d %B %Y · %H:%M UTC"),
    }

# ── GENERATE HTML ──────────────────────────────────────────
def generate_html(wellness, activities, summary):
    s = summary

    # Chart data from wellness series (has ctl, atl per day)
    chart_data = []
    for w in wellness:
        ctl = w.get("ctl")
        atl = w.get("atl")
        tsb = round(ctl - atl, 1) if (ctl is not None and atl is not None) else None
        chart_data.append({
            "date": (w.get("id") or "")[:10],
            "ctl":  round(ctl, 1) if ctl is not None else None,
            "atl":  round(atl, 1) if atl is not None else None,
            "tsb":  tsb,
        })

    # Activity rows
    act_rows = []
    for a in reversed(activities[-10:]):
        wkg = round(a["weighted_average_watts"] / ATHLETE["weight_kg"], 2) if a.get("weighted_average_watts") else None
        act_rows.append({
            "date": (a.get("start_date_local") or "")[:10],
            "name": a.get("name") or "Ride",
            "dist": round(a["distance"] / 1000, 1)         if a.get("distance")               else None,
            "time": round(a["moving_time"] / 60)           if a.get("moving_time")             else None,
            "tss":  round(a["icu_training_load"])          if a.get("icu_training_load")       else None,
            "np":   round(a["weighted_average_watts"])     if a.get("weighted_average_watts")  else None,
            "hr":   round(a["average_heartrate"])          if a.get("average_heartrate")       else None,
            "wkg":  wkg,
            "elev": round(a["total_elevation_gain"])       if a.get("total_elevation_gain")    else None,
        })

    tsb_display = (("+" if s["tsb"] > 0 else "") + str(s["tsb"])) if s["tsb"] is not None else "—"
    max_tss = max((a["tss"] or 0 for a in act_rows), default=1)

    act_html = ""
    for a in act_rows:
        bar_w = round((a["tss"] or 0) / max_tss * 100) if max_tss else 0
        tss_bar = f'<div class="tss-bar" style="width:{bar_w}px"></div>' if a["tss"] else ""
        act_html += f"""<tr>
        <td><span class="muted">{a['date']}</span></td>
        <td><div class="act-name">{a['name']}</div></td>
        <td><span class="big">{a['dist'] or '—'}</span><span class="unit">km</span></td>
        <td><span class="big">{a['time'] or '—'}</span><span class="unit">min</span></td>
        <td><span class="big">{a['tss'] or '—'}</span><span class="unit">tss</span>{tss_bar}</td>
        <td><span class="big">{a['np'] or '—'}</span><span class="unit">w</span></td>
        <td><span class="big">{a['wkg'] or '—'}</span><span class="unit">w/kg</span></td>
        <td><span class="big">{a['hr'] or '—'}</span><span class="unit">bpm</span></td>
      </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>David Moreno · Cycling Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;700;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
:root{{--bg:#090b0e;--surf:#0f1318;--surf2:#141920;--border:#1c2330;
      --accent:#e8ff47;--blue:#47c8ff;--red:#ff5252;--orange:#ffaa47;
      --text:#dde2ec;--muted:#4a5568;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;font-size:13px;}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 16px 100px;}}
.hdr{{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;
      padding-bottom:20px;border-bottom:1px solid var(--border);margin-bottom:8px;}}
.hdr-name{{font-family:'Barlow Condensed',sans-serif;font-size:52px;font-weight:900;letter-spacing:-2px;line-height:1;}}
.hdr-name span{{color:var(--accent);}}
.hdr-sub{{color:var(--muted);font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}}
.badge{{display:inline-flex;align-items:center;gap:7px;padding:8px 16px;border-radius:3px;
        font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;}}
.badge.ready  {{background:rgba(232,255,71,.1);color:var(--accent);border:1px solid rgba(232,255,71,.25);}}
.badge.caution{{background:rgba(255,170,71,.1);color:var(--orange);border:1px solid rgba(255,170,71,.25);}}
.badge.rest   {{background:rgba(255,82,82,.1); color:var(--red);   border:1px solid rgba(255,82,82,.25);}}
.dot{{width:7px;height:7px;border-radius:50%;background:currentColor;animation:pulse 2s infinite;}}
.updated{{color:var(--muted);font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
          text-align:right;margin:10px 0 20px;}}
.row{{display:grid;gap:12px;margin-bottom:12px;}}
.row3{{grid-template-columns:repeat(3,1fr);}}
.row4{{grid-template-columns:repeat(4,1fr);}}
.row4b{{grid-template-columns:repeat(4,1fr);}}
@media(max-width:600px){{.row4,.row4b{{grid-template-columns:repeat(2,1fr);}}}}
.card{{background:var(--surf);border:1px solid var(--border);border-radius:4px;padding:18px;}}
.card-title{{font-family:'Barlow Condensed',sans-serif;font-size:12px;font-weight:600;
             color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;}}
.kpi{{position:relative;overflow:hidden;}}
.kpi::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;}}
.kpi.ctl::after{{background:#47c8ff;}} .kpi.atl::after{{background:#ff5252;}} .kpi.tsb::after{{background:#e8ff47;}}
.kpi-val{{font-family:'Barlow Condensed',sans-serif;font-size:56px;font-weight:900;letter-spacing:-2px;line-height:1;}}
.kpi.ctl .kpi-val{{color:#47c8ff;}} .kpi.atl .kpi-val{{color:#ff5252;}} .kpi.tsb .kpi-val{{color:#e8ff47;}}
.kpi-sub{{color:var(--muted);font-size:10px;margin-top:5px;letter-spacing:1px;text-transform:uppercase;}}
.well-val{{font-family:'Barlow Condensed',sans-serif;font-size:34px;font-weight:800;line-height:1;}}
.well-unit{{color:var(--muted);font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-top:3px;}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;}}
.leg{{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--muted);letter-spacing:1.5px;text-transform:uppercase;}}
.leg-dot{{width:10px;height:3px;border-radius:2px;}}
.act-table{{width:100%;border-collapse:collapse;}}
.act-table th{{color:var(--muted);font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
               text-align:right;padding:6px 8px;border-bottom:1px solid var(--border);font-weight:400;}}
.act-table th:first-child,.act-table th:nth-child(2){{text-align:left;}}
.act-table td{{padding:10px 8px;border-bottom:1px solid rgba(28,35,48,.6);font-size:12px;
               text-align:right;vertical-align:middle;}}
.act-table td:first-child,.act-table td:nth-child(2){{text-align:left;}}
.act-table tr:last-child td{{border-bottom:none;}}
.act-table tr:hover td{{background:rgba(255,255,255,.02);}}
.act-name{{font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.big{{font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:700;}}
.unit{{color:var(--muted);font-size:9px;display:block;letter-spacing:1px;}}
.muted{{color:var(--muted);font-size:11px;}}
.tss-bar{{height:3px;background:var(--accent);border-radius:2px;margin-top:4px;min-width:2px;}}
.brief-box{{background:var(--surf2);border:1px solid var(--border);border-left:3px solid var(--blue);
            border-radius:4px;padding:20px;margin-bottom:12px;}}
.brief-box h3{{font-family:'Barlow Condensed',sans-serif;font-size:16px;font-weight:700;
               color:var(--blue);letter-spacing:1px;margin-bottom:14px;}}
.brief-text{{white-space:pre-wrap;font-size:12px;line-height:1.9;color:var(--text);}}
.copy-btn{{margin-top:14px;padding:8px 20px;background:var(--blue);color:#090b0e;
           border:none;border-radius:3px;font-family:'Barlow Condensed',sans-serif;
           font-size:15px;font-weight:700;letter-spacing:1px;cursor:pointer;transition:opacity .2s;}}
.copy-btn:hover{{opacity:.85;}}
@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.3;}}}}
</style>
</head>
<body>
<div class="wrap">

<div class="hdr">
  <div>
    <div class="hdr-name">DAVID <span>MORENO</span></div>
    <div class="hdr-sub">Capos Team &middot; Amateur Cyclist &middot; 38y &middot; 79kg &middot; 1.85m</div>
  </div>
  <div class="badge {s['status']}"><div class="dot"></div>{s['status_label']}</div>
</div>
<div class="updated">Last updated: {s['updated']}</div>

<!-- CTL / ATL / TSB -->
<div class="row row3">
  <div class="card kpi ctl">
    <div class="card-title">CTL &middot; Fitness</div>
    <div class="kpi-val">{s['ctl'] if s['ctl'] is not None else '—'}</div>
    <div class="kpi-sub">Chronic Training Load</div>
  </div>
  <div class="card kpi atl">
    <div class="card-title">ATL &middot; Fatigue</div>
    <div class="kpi-val">{s['atl'] if s['atl'] is not None else '—'}</div>
    <div class="kpi-sub">Acute Training Load</div>
  </div>
  <div class="card kpi tsb">
    <div class="card-title">TSB &middot; Form</div>
    <div class="kpi-val">{tsb_display}</div>
    <div class="kpi-sub">Fitness minus Fatigue</div>
  </div>
</div>

<!-- WELLNESS ROW 1 -->
<div class="row row4">
  <div class="card">
    <div class="card-title">Resting HR</div>
    <div class="well-val">{s['resting_hr'] or '—'}</div>
    <div class="well-unit">BPM</div>
  </div>
  <div class="card">
    <div class="card-title">HRV</div>
    <div class="well-val">{s['hrv'] or '—'}</div>
    <div class="well-unit">ms</div>
  </div>
  <div class="card">
    <div class="card-title">Sleep</div>
    <div class="well-val">{s['sleep_hrs'] or '—'}</div>
    <div class="well-unit">hours</div>
  </div>
  <div class="card">
    <div class="card-title">Sleep Score</div>
    <div class="well-val">{s['sleep_score'] or '—'}</div>
    <div class="well-unit">/ 100</div>
  </div>
</div>

<!-- WELLNESS ROW 2 -->
<div class="row row4b">
  <div class="card">
    <div class="card-title">Readiness</div>
    <div class="well-val">{s['readiness'] or '—'}</div>
    <div class="well-unit">/ 100</div>
  </div>
  <div class="card">
    <div class="card-title">SpO2</div>
    <div class="well-val">{s['spo2'] or '—'}</div>
    <div class="well-unit">%</div>
  </div>
  <div class="card">
    <div class="card-title">Fatigue</div>
    <div class="well-val">{s['fatigue'] or '—'}</div>
    <div class="well-unit">/ 7</div>
  </div>
  <div class="card">
    <div class="card-title">Soreness</div>
    <div class="well-val">{s['soreness'] or '—'}</div>
    <div class="well-unit">/ 7</div>
  </div>
</div>

<!-- CHART -->
<div class="card" style="margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
    <div class="card-title" style="margin:0;">Performance Management · 60 Days</div>
    <div class="legend">
      <div class="leg"><div class="leg-dot" style="background:#47c8ff"></div>CTL</div>
      <div class="leg"><div class="leg-dot" style="background:#ff5252"></div>ATL</div>
      <div class="leg"><div class="leg-dot" style="background:#e8ff47"></div>TSB</div>
    </div>
  </div>
  <canvas id="chart" height="200"></canvas>
</div>

<!-- ACTIVITIES -->
<div class="card" style="margin-bottom:12px;">
  <div class="card-title">Recent Activities</div>
  <div style="overflow-x:auto;">
  <table class="act-table">
    <thead><tr>
      <th>Date</th><th>Activity</th>
      <th>km</th><th>min</th><th>TSS</th><th>NP</th><th>W/kg</th><th>HR</th>
    </tr></thead>
    <tbody>{act_html}</tbody>
  </table>
  </div>
</div>

<!-- CLAUDE BRIEF -->
<div class="brief-box">
  <h3>🤖 CLAUDE DAILY BRIEF — Copy &amp; Paste into Claude.ai</h3>
  <div class="brief-text" id="briefText">{s['brief']}</div>
  <button class="copy-btn" onclick="copyBrief()">📋 COPY TO CLIPBOARD</button>
</div>

</div>
<script>
const RAW = {json.dumps(chart_data)};
window.addEventListener('load', () => {{
  const canvas = document.getElementById('chart');
  canvas.width = canvas.parentElement.offsetWidth;
  const ctx = canvas.getContext('2d');
  const pts = RAW.filter(d => d.ctl !== null);
  if (!pts.length) return;
  const pad = {{t:10,r:10,b:28,l:44}};
  const W = canvas.width - pad.l - pad.r;
  const H = canvas.height - pad.t - pad.b;
  const vals = pts.flatMap(p=>[p.ctl,p.atl,p.tsb]).filter(v=>v!=null);
  const minV = Math.min(...vals) - 5;
  const maxV = Math.max(...vals) + 5;
  const xS = i => pad.l + (i / (pts.length - 1)) * W;
  const yS = v => pad.t + H - ((v - minV) / (maxV - minV)) * H;
  // Grid
  for (let i = 0; i <= 4; i++) {{
    const y = pad.t + (H / 4) * i;
    ctx.strokeStyle = '#1c2330'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + W, y); ctx.stroke();
    ctx.fillStyle = '#4a5568'; ctx.font = '9px JetBrains Mono'; ctx.textAlign = 'right';
    ctx.fillText(Math.round(maxV - ((maxV - minV) / 4) * i), pad.l - 4, y + 4);
  }}
  // Zero line
  if (minV < 0 && maxV > 0) {{
    ctx.strokeStyle = 'rgba(232,255,71,.15)'; ctx.setLineDash([4,4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, yS(0)); ctx.lineTo(pad.l + W, yS(0)); ctx.stroke();
    ctx.setLineDash([]);
  }}
  function line(key, color, lw) {{
    ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.beginPath(); let started = false;
    pts.forEach((p, i) => {{
      if (p[key] == null) return;
      if (!started) {{ ctx.moveTo(xS(i), yS(p[key])); started = true; }}
      else ctx.lineTo(xS(i), yS(p[key]));
    }});
    ctx.stroke();
  }}
  line('atl', '#ff5252', 1.5);
  line('tsb', '#e8ff47', 1.5);
  line('ctl', '#47c8ff', 2.5);
  // X labels
  ctx.fillStyle = '#4a5568'; ctx.font = '9px JetBrains Mono'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(pts.length / 7));
  pts.forEach((p, i) => {{
    if (i % step === 0) ctx.fillText(p.date.slice(5), xS(i), canvas.height - 6);
  }});
}});
function copyBrief() {{
  navigator.clipboard.writeText(document.getElementById('briefText').innerText).then(() => {{
    const b = document.querySelector('.copy-btn');
    b.textContent = '✓ COPIED!';
    setTimeout(() => b.textContent = '📋 COPY TO CLIPBOARD', 2500);
  }});
}}
</script>
</body>
</html>"""
    return html

# ── MAIN ───────────────────────────────────────────────────
def main():
    print(f"🚴 Building dashboard for {ATHLETE['name']}...")
    wellness, activities = fetch_all()

    print("📊 Computing summary...")
    summary = compute_summary(wellness, activities)
    print(f"   CTL={summary['ctl']} ATL={summary['atl']} TSB={summary['tsb']}")
    print(f"   HRV={summary['hrv']} RestHR={summary['resting_hr']} Sleep={summary['sleep_hrs']}h")
    print(f"   Status: {summary['status_label']}")

    print("🎨 Generating HTML...")
    html = generate_html(wellness, activities, summary)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Done! index.html written ({len(html):,} bytes)")

if __name__ == "__main__":
    main()
