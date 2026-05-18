#!/usr/bin/env python3
"""
🚴 David Moreno — Daily Cycling Dashboard Builder
Runs on GitHub Actions every morning:
1. Fetches data from Intervals.icu API (server-side, no CORS issues)
2. Generates a static index.html dashboard with data baked in
3. GitHub Actions commits it back → GitHub Pages serves it live
"""

import os
import json
import requests
from base64 import b64encode
from datetime import datetime, timedelta

# ── CREDENTIALS (from GitHub Secrets) ─────────────────────
ATHLETE_ID    = os.environ.get("INTERVALS_ATHLETE_ID", "45826670")
API_KEY       = os.environ["INTERVALS_API_KEY"]
AUTH_HEADER   = {"Authorization": "Basic " + b64encode(f"API_KEY:{API_KEY}".encode()).decode()}
BASE_URL      = "https://intervals.icu/api/v1/athlete/0"   # "0" = current athlete

ATHLETE = {
    "name":      "David Moreno",
    "team":      "Capos Team",
    "age":       38,
    "weight_kg": 79,
    "height_m":  1.85,
}

# ── HELPERS ────────────────────────────────────────────────
def date_str(days_back=0):
    return (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

def get(path, params=None):
    url = f"{BASE_URL}{path}"
    r = requests.get(url, headers=AUTH_HEADER, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

# ── FETCH ──────────────────────────────────────────────────
def fetch_all():
    print("📡 Fetching fitness data (60 days)...")
    fitness = get("/fitness-data", {"oldest": date_str(60), "newest": date_str(0)})

    print("📡 Fetching wellness data (30 days)...")
    wellness = get("/wellness", {"oldest": date_str(30), "newest": date_str(0)})

    print("📡 Fetching recent activities (30 days)...")
    activities = get("/activities", {
        "oldest": date_str(30) + "T00:00:00",
        "newest": date_str(0)  + "T23:59:59",
    })

    return fitness, wellness, activities

# ── COMPUTE SUMMARY ────────────────────────────────────────
def compute_summary(fitness, wellness, activities):
    lat_fit  = fitness[-1]  if fitness  else {}
    lat_well = wellness[-1] if wellness else {}

    ctl = lat_fit.get("ctl")
    atl = lat_fit.get("atl")
    tsb = lat_fit.get("tsb")

    if tsb is None:
        status, status_label = "ready", "🟢 READY TO TRAIN"
    elif tsb < -20:
        status, status_label = "rest",    "🔴 REST DAY"
    elif tsb < -5:
        status, status_label = "caution", "🟡 TAKE IT EASY"
    else:
        status, status_label = "ready",   "🟢 READY TO TRAIN"

    # Build Claude brief text
    act_lines = []
    for a in reversed(activities[-7:]):
        d    = (a.get("start_date_local") or "")[:10]
        dist = f"{a['distance']/1000:.1f}km" if a.get("distance") else ""
        tss  = f"TSS:{round(a['icu_training_load'])}" if a.get("icu_training_load") else ""
        np   = f"NP:{round(a['weighted_average_watts'])}w" if a.get("weighted_average_watts") else ""
        hr   = f"HR:{round(a['average_heartrate'])}" if a.get("average_heartrate") else ""
        act_lines.append(f"  • {d} — {a.get('name','Ride')} {dist} {tss} {np} {hr}".strip())

    sleep_hrs = ""
    if lat_well.get("sleepSecs"):
        sleep_hrs = f"{lat_well['sleepSecs']/3600:.1f} hrs"

    brief = f"""📋 DAILY TRAINING DATA — {datetime.utcnow().strftime('%A, %d %B %Y')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

👤 ATHLETE: {ATHLETE['name']} | {ATHLETE['age']}y | {ATHLETE['weight_kg']}kg | {ATHLETE['height_m']}m | {ATHLETE['team']}

📊 PERFORMANCE MANAGEMENT (TODAY):
  • CTL (Fitness):  {round(ctl) if ctl is not None else 'N/A'}
  • ATL (Fatigue):  {round(atl) if atl is not None else 'N/A'}
  • TSB (Form):     {round(tsb) if tsb is not None else 'N/A'}

😴 WELLNESS (LATEST):
  • Resting HR:     {f"{round(lat_well['restingHR'])} bpm" if lat_well.get('restingHR') else 'N/A'}
  • HRV:            {f"{round(lat_well['hrv'])} ms"        if lat_well.get('hrv')        else 'N/A'}
  • Sleep:          {sleep_hrs or 'N/A'}
  • Sleep quality:  {f"{lat_well['sleepQuality']}/5"       if lat_well.get('sleepQuality') else 'N/A'}
  • Fatigue:        {f"{lat_well['fatigue']}/7"            if lat_well.get('fatigue')     else 'N/A'}
  • Soreness:       {f"{lat_well['soreness']}/7"           if lat_well.get('soreness')    else 'N/A'}
  • Mood:           {f"{lat_well['mood']}/7"               if lat_well.get('mood')        else 'N/A'}

🚴 LAST 7 ACTIVITIES:
{chr(10).join(act_lines) if act_lines else '  No recent activities'}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Paste into Claude.ai and ask:
"Analyse my training and give me today's coaching plan"
"""

    return {
        "ctl": round(ctl) if ctl is not None else None,
        "atl": round(atl) if atl is not None else None,
        "tsb": round(tsb) if tsb is not None else None,
        "status": status,
        "status_label": status_label,
        "resting_hr":    round(lat_well["restingHR"])          if lat_well.get("restingHR")    else None,
        "hrv":           round(lat_well["hrv"])                if lat_well.get("hrv")          else None,
        "sleep_hrs":     round(lat_well["sleepSecs"]/3600, 1) if lat_well.get("sleepSecs")    else None,
        "sleep_quality": lat_well.get("sleepQuality"),
        "fatigue":       lat_well.get("fatigue"),
        "soreness":      lat_well.get("soreness"),
        "mood":          lat_well.get("mood"),
        "brief":         brief,
        "updated":       datetime.utcnow().strftime("%A %d %B %Y · %H:%M UTC"),
    }

# ── GENERATE HTML ──────────────────────────────────────────
def generate_html(fitness, wellness, activities, summary):
    # Prepare chart data (last 60 days)
    chart_data = []
    for d in fitness:
        chart_data.append({
            "date": (d.get("date") or "")[:10],
            "ctl":  round(d["ctl"],  1) if d.get("ctl")  is not None else None,
            "atl":  round(d["atl"],  1) if d.get("atl")  is not None else None,
            "tsb":  round(d["tsb"],  1) if d.get("tsb")  is not None else None,
        })

    # Wellness sparkline (last 30 days)
    well_data = []
    for w in wellness:
        well_data.append({
            "date": (w.get("id") or "")[:10],
            "hrv":  round(w["hrv"]) if w.get("hrv") else None,
            "hr":   round(w["restingHR"]) if w.get("restingHR") else None,
            "sleep": round(w["sleepSecs"]/3600, 1) if w.get("sleepSecs") else None,
        })

    # Recent activities (last 10)
    act_rows = []
    for a in reversed(activities[-10:]):
        act_rows.append({
            "date":  (a.get("start_date_local") or "")[:10],
            "name":  a.get("name") or "Ride",
            "type":  a.get("type") or "",
            "dist":  round(a["distance"]/1000, 1) if a.get("distance") else None,
            "time":  round(a["moving_time"]/60)   if a.get("moving_time") else None,
            "tss":   round(a["icu_training_load"]) if a.get("icu_training_load") else None,
            "np":    round(a["weighted_average_watts"]) if a.get("weighted_average_watts") else None,
            "hr":    round(a["average_heartrate"])      if a.get("average_heartrate") else None,
            "wkg":   round(a["weighted_average_watts"] / ATHLETE["weight_kg"], 2) if a.get("weighted_average_watts") else None,
            "elev":  round(a["total_elevation_gain"])   if a.get("total_elevation_gain") else None,
        })

    s = summary
    tsb_display = (("+" if s["tsb"] > 0 else "") + str(s["tsb"])) if s["tsb"] is not None else "—"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>David Moreno · Cycling Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@300;400;600;700;800;900&family=JetBrains+Mono:wght@300;400;500&display=swap" rel="stylesheet"/>
<style>
:root {{
  --bg:      #090b0e;
  --surf:    #0f1318;
  --surf2:   #141920;
  --border:  #1c2330;
  --accent:  #e8ff47;
  --blue:    #47c8ff;
  --red:     #ff5252;
  --orange:  #ffaa47;
  --text:    #dde2ec;
  --muted:   #4a5568;
  --ctl:     #47c8ff;
  --atl:     #ff5252;
  --tsb:     #e8ff47;
}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--text);font-family:'JetBrains Mono',monospace;font-size:13px;line-height:1.5;}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 16px 100px;}}

/* HEADER */
.hdr{{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:12px;
      padding-bottom:20px;border-bottom:1px solid var(--border);margin-bottom:28px;}}
.hdr-name{{font-family:'Barlow Condensed',sans-serif;font-size:52px;font-weight:900;
           letter-spacing:-2px;line-height:1;}}
.hdr-name span{{color:var(--accent);}}
.hdr-sub{{color:var(--muted);font-size:11px;letter-spacing:2px;text-transform:uppercase;margin-top:4px;}}
.badge{{display:inline-flex;align-items:center;gap:7px;padding:8px 16px;border-radius:3px;
        font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;}}
.badge.ready  {{background:rgba(232,255,71,.1);color:var(--accent);border:1px solid rgba(232,255,71,.25);}}
.badge.caution{{background:rgba(255,170,71,.1);color:var(--orange);border:1px solid rgba(255,170,71,.25);}}
.badge.rest   {{background:rgba(255,82,82,.1); color:var(--red);   border:1px solid rgba(255,82,82,.25);}}
.dot{{width:7px;height:7px;border-radius:50%;background:currentColor;animation:pulse 2s infinite;}}

/* GRID HELPERS */
.row{{display:grid;gap:12px;margin-bottom:12px;}}
.row3{{grid-template-columns:repeat(3,1fr);}}
.row4{{grid-template-columns:repeat(4,1fr);}}
@media(max-width:600px){{.row3{{grid-template-columns:repeat(3,1fr);}}.row4{{grid-template-columns:repeat(2,1fr);}}}}

/* CARDS */
.card{{background:var(--surf);border:1px solid var(--border);border-radius:4px;padding:18px;}}
.card-title{{font-family:'Barlow Condensed',sans-serif;font-size:13px;font-weight:600;
             color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:14px;}}

/* KPI */
.kpi{{position:relative;overflow:hidden;}}
.kpi::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:2px;}}
.kpi.ctl::after{{background:var(--ctl);}}
.kpi.atl::after{{background:var(--atl);}}
.kpi.tsb::after{{background:var(--tsb);}}
.kpi-val{{font-family:'Barlow Condensed',sans-serif;font-size:56px;font-weight:900;
          letter-spacing:-2px;line-height:1;}}
.kpi.ctl .kpi-val{{color:var(--ctl);}}
.kpi.atl .kpi-val{{color:var(--atl);}}
.kpi.tsb .kpi-val{{color:var(--tsb);}}
.kpi-sub{{color:var(--muted);font-size:10px;margin-top:5px;letter-spacing:1px;text-transform:uppercase;}}

/* WELLNESS */
.well-val{{font-family:'Barlow Condensed',sans-serif;font-size:36px;font-weight:800;line-height:1;}}
.well-unit{{color:var(--muted);font-size:10px;letter-spacing:1px;text-transform:uppercase;margin-top:3px;}}

/* CHART */
.chart-wrap{{position:relative;}}
canvas{{width:100%!important;display:block;}}
.legend{{display:flex;gap:20px;flex-wrap:wrap;}}
.leg{{display:flex;align-items:center;gap:6px;font-size:10px;color:var(--muted);
      letter-spacing:1.5px;text-transform:uppercase;}}
.leg-dot{{width:10px;height:3px;border-radius:2px;}}

/* ACTIVITIES TABLE */
.act-table{{width:100%;border-collapse:collapse;}}
.act-table th{{color:var(--muted);font-size:10px;letter-spacing:1.5px;text-transform:uppercase;
               text-align:right;padding:6px 8px;border-bottom:1px solid var(--border);font-weight:400;}}
.act-table th:first-child,.act-table th:nth-child(2){{text-align:left;}}
.act-table td{{padding:10px 8px;border-bottom:1px solid rgba(28,35,48,.6);font-size:12px;
               text-align:right;vertical-align:middle;}}
.act-table td:first-child,.act-table td:nth-child(2){{text-align:left;}}
.act-table tr:last-child td{{border-bottom:none;}}
.act-table tr:hover td{{background:rgba(255,255,255,.02);}}
.act-name{{font-size:12px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}}
.act-date{{color:var(--muted);font-size:11px;}}
.big{{font-family:'Barlow Condensed',sans-serif;font-size:20px;font-weight:700;}}
.unit{{color:var(--muted);font-size:9px;display:block;letter-spacing:1px;}}
.tss-bar{{height:3px;background:var(--accent);border-radius:2px;margin-top:4px;min-width:2px;}}

/* BRIEF */
.brief-box{{background:var(--surf2);border:1px solid var(--border);border-left:3px solid var(--blue);
            border-radius:4px;padding:20px;margin-bottom:12px;}}
.brief-box h3{{font-family:'Barlow Condensed',sans-serif;font-size:16px;font-weight:700;
               color:var(--blue);letter-spacing:1px;margin-bottom:14px;}}
.brief-text{{white-space:pre-wrap;font-size:12px;line-height:1.9;color:var(--text);}}
.copy-btn{{margin-top:14px;padding:8px 20px;background:var(--blue);color:#090b0e;
           border:none;border-radius:3px;font-family:'Barlow Condensed',sans-serif;
           font-size:15px;font-weight:700;letter-spacing:1px;cursor:pointer;transition:opacity .2s;}}
.copy-btn:hover{{opacity:.85;}}

/* FOOTER */
.updated{{color:var(--muted);font-size:10px;letter-spacing:1.5px;text-align:right;
          margin-bottom:20px;text-transform:uppercase;}}

@keyframes pulse{{0%,100%{{opacity:1;}}50%{{opacity:.3;}}}}
</style>
</head>
<body>
<div class="wrap">

<!-- HEADER -->
<div class="hdr">
  <div>
    <div class="hdr-name">DAVID <span>MORENO</span></div>
    <div class="hdr-sub">Capos Team &middot; Amateur Cyclist &middot; 38y &middot; 79kg &middot; 1.85m</div>
  </div>
  <div class="badge {s['status']}">
    <div class="dot"></div>{s['status_label']}
  </div>
</div>

<div class="updated">Last updated: {s['updated']}</div>

<!-- KPI ROW -->
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

<!-- WELLNESS ROW -->
<div class="row row4">
  <div class="card">
    <div class="card-title">Resting HR</div>
    <div class="well-val">{s['resting_hr'] if s['resting_hr'] else '—'}</div>
    <div class="well-unit">BPM</div>
  </div>
  <div class="card">
    <div class="card-title">HRV</div>
    <div class="well-val">{s['hrv'] if s['hrv'] else '—'}</div>
    <div class="well-unit">ms</div>
  </div>
  <div class="card">
    <div class="card-title">Sleep</div>
    <div class="well-val">{s['sleep_hrs'] if s['sleep_hrs'] else '—'}</div>
    <div class="well-unit">hours</div>
  </div>
  <div class="card">
    <div class="card-title">Fatigue</div>
    <div class="well-val">{s['fatigue'] if s['fatigue'] else '—'}</div>
    <div class="well-unit">/ 7</div>
  </div>
</div>

<!-- FITNESS CHART -->
<div class="card" style="margin-bottom:12px;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:16px;">
    <div class="card-title" style="margin:0;">Performance Management · 60 Days</div>
    <div class="legend">
      <div class="leg"><div class="leg-dot" style="background:var(--ctl)"></div>CTL</div>
      <div class="leg"><div class="leg-dot" style="background:var(--atl)"></div>ATL</div>
      <div class="leg"><div class="leg-dot" style="background:var(--tsb)"></div>TSB</div>
    </div>
  </div>
  <canvas id="chart" height="200"></canvas>
</div>

<!-- ACTIVITIES TABLE -->
<div class="card" style="margin-bottom:12px;">
  <div class="card-title">Recent Activities</div>
  <div style="overflow-x:auto;">
  <table class="act-table">
    <thead>
      <tr>
        <th>Date</th><th>Activity</th>
        <th>km</th><th>min</th><th>TSS</th>
        <th>NP (w)</th><th>W/kg</th><th>HR</th>
      </tr>
    </thead>
    <tbody>
"""

    max_tss = max((a["tss"] or 0 for a in act_rows), default=1)
    for a in act_rows:
        bar_w = round((a["tss"] or 0) / max_tss * 120) if max_tss else 0
        html += f"""      <tr>
        <td><span class="act-date">{a['date']}</span></td>
        <td><div class="act-name">{a['name']}</div></td>
        <td><span class="big">{a['dist'] or '—'}</span><span class="unit">km</span></td>
        <td><span class="big">{a['time'] or '—'}</span><span class="unit">min</span></td>
        <td>
          <span class="big">{a['tss'] or '—'}</span><span class="unit">tss</span>
          {'<div class="tss-bar" style="width:'+str(bar_w)+'px"></div>' if a['tss'] else ''}
        </td>
        <td><span class="big">{a['np'] or '—'}</span><span class="unit">w</span></td>
        <td><span class="big">{a['wkg'] or '—'}</span><span class="unit">w/kg</span></td>
        <td><span class="big">{a['hr'] or '—'}</span><span class="unit">bpm</span></td>
      </tr>
"""

    html += f"""    </tbody>
  </table>
  </div>
</div>

<!-- CLAUDE BRIEF -->
<div class="brief-box">
  <h3>🤖 CLAUDE DAILY BRIEF — Copy &amp; Paste into Claude.ai</h3>
  <div class="brief-text" id="briefText">{summary['brief']}</div>
  <button class="copy-btn" onclick="copyBrief()">📋 COPY TO CLIPBOARD</button>
</div>

</div><!-- /wrap -->

<script>
// ── CHART ──────────────────────────────────────────────────
const RAW = {json.dumps(chart_data)};

window.addEventListener('load', () => {{
  const canvas = document.getElementById('chart');
  canvas.width  = canvas.parentElement.offsetWidth;
  canvas.height = 200;
  const ctx = canvas.getContext('2d');
  const pts = RAW.filter(d => d.ctl !== null);
  if (!pts.length) return;

  const pad = {{t:10, r:10, b:28, l:40}};
  const W = canvas.width  - pad.l - pad.r;
  const H = canvas.height - pad.t - pad.b;
  const vals = pts.flatMap(p => [p.ctl, p.atl, p.tsb]).filter(v => v != null);
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

  // Zero line for TSB
  if (minV < 0 && maxV > 0) {{
    ctx.strokeStyle = 'rgba(232,255,71,.15)';
    ctx.setLineDash([4, 4]); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(pad.l, yS(0)); ctx.lineTo(pad.l + W, yS(0)); ctx.stroke();
    ctx.setLineDash([]);
  }}

  function drawLine(key, color, lw) {{
    ctx.strokeStyle = color; ctx.lineWidth = lw; ctx.beginPath();
    let started = false;
    pts.forEach((p, i) => {{
      if (p[key] == null) return;
      if (!started) {{ ctx.moveTo(xS(i), yS(p[key])); started = true; }}
      else ctx.lineTo(xS(i), yS(p[key]));
    }});
    ctx.stroke();
  }}

  drawLine('atl', '#ff5252', 1.5);
  drawLine('tsb', '#e8ff47', 1.5);
  drawLine('ctl', '#47c8ff', 2.5);

  // X labels
  ctx.fillStyle = '#4a5568'; ctx.font = '9px JetBrains Mono'; ctx.textAlign = 'center';
  const step = Math.max(1, Math.floor(pts.length / 7));
  pts.forEach((p, i) => {{
    if (i % step === 0) ctx.fillText(p.date.slice(5), xS(i), canvas.height - 6);
  }});
}});

// ── COPY ───────────────────────────────────────────────────
function copyBrief() {{
  const text = document.getElementById('briefText').innerText;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.querySelector('.copy-btn');
    btn.textContent = '✓ COPIED!';
    setTimeout(() => btn.textContent = '📋 COPY TO CLIPBOARD', 2500);
  }});
}}
</script>
</body>
</html>"""

    return html

# ── MAIN ───────────────────────────────────────────────────
def main():
    print(f"🚴 Building dashboard for {ATHLETE['name']}...")
    fitness, wellness, activities = fetch_all()

    print("📊 Computing summary...")
    summary = compute_summary(fitness, wellness, activities)

    print(f"   Status : {summary['status_label']}")
    print(f"   CTL/ATL/TSB : {summary['ctl']} / {summary['atl']} / {summary['tsb']}")
    print(f"   Activities fetched: {len(activities)}")

    print("🎨 Generating HTML dashboard...")
    html = generate_html(fitness, wellness, activities, summary)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print("✅ index.html written successfully!")
    print(f"   Size: {len(html):,} bytes")

if __name__ == "__main__":
    main()
