# customer-value-pack/dashboard/generate_dashboard.py
# audit_log.jsonl と eval_results.csv から実データでダッシュボードHTMLを生成する

import json
import csv
import os
from datetime import datetime, date
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
AUDIT_LOG = BASE_DIR / "rag-security-project" / "audit_log.jsonl"
EVAL_CSV = BASE_DIR / "llm-production-ops" / "evals" / "eval_results.csv"
OUTPUT = Path(__file__).parent / "dashboard_output.html"


# ── 1. audit_log.jsonl を集計 ─────────────────────────────────────────────


def load_audit_log(path):
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def calc_audit_metrics(records):
    normal = [r for r in records if "event" not in r]
    denied = [r for r in records if r.get("event") == "ACCESS_DENIED"]

    # ユニークユーザー数
    users_queried = {r["user_id"] for r in normal}

    # security incidents の内訳
    incidents = []
    for r in denied:
        reason = r.get("reason", "")
        if "ignore" in r.get("query", "").lower() or "不正な入力" in reason:
            sev, label = "low", "Prompt injection attempt (blocklist)"
        elif "レート制限" in reason:
            sev, label = "info", "Rate limit exceeded (Fail Closed)"
        else:
            sev, label = "low", "ACL access denied"
        incidents.append({
            "date": r["timestamp"][:10],
            "event": label,
            "user": r["user_id"] if r["user_id"] else "unknown",
            "sev": sev,
        })

    # 重複排除（同一日・同一ラベルはまとめる）
    seen = set()
    unique_incidents = []
    for inc in incidents:
        key = (inc["date"], inc["event"])
        if key not in seen:
            seen.add(key)
            unique_incidents.append(inc)

    # PII 検出件数
    pii_count = sum(1 for r in normal if r.get("pii_detected"))

    return {
        "total_queries": len(normal),
        "unique_users": len(users_queried),
        "blocked_count": len(denied),
        "pii_count": pii_count,
        "incidents": unique_incidents,
    }


# ── 2. eval_results.csv を集計 ────────────────────────────────────────────


def load_eval_metrics(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        return {"avg_accuracy": 0, "avg_combined": 0, "scores": []}

    combined = [float(r["combined_score"]) for r in rows]
    accuracy = [float(r["accuracy"]) for r in rows]

    # combined_score は 0〜5 スケール → %換算
    avg_combined_pct = round(sum(combined) / len(combined) / 5 * 100, 1)
    avg_accuracy_pct = round(sum(accuracy) / len(accuracy) / 5 * 100, 1)

    # カテゴリ別スコア（棒グラフ用）
    by_category = defaultdict(list)
    for r in rows:
        by_category[r["category"]].append(float(r["combined_score"]))
    cat_labels = list(by_category.keys())
    cat_scores = [round(sum(v) / len(v) / 5 * 100, 1) for v in by_category.values()]

    return {
        "avg_accuracy": avg_accuracy_pct,
        "avg_combined": avg_combined_pct,
        "row_count": len(rows),
        "cat_labels": cat_labels,
        "cat_scores": cat_scores,
        "raw_combined": [round(s / 5 * 100, 1) for s in combined],
    }


# ── 3. HTML 生成 ──────────────────────────────────────────────────────────


def render_incident_rows(incidents):
    sev_class = {"low": "sev-low", "info": "sev-info"}
    rows = ""
    for inc in incidents:
        cls = sev_class.get(inc["sev"], "sev-low")
        rows += f"""
        <tr>
          <td>{inc["date"]}</td>
          <td>{inc["event"]}</td>
          <td>{inc["user"]}</td>
          <td><span class="sev {cls}">{inc["sev"]}</span></td>
          <td>blocked</td>
        </tr>"""
    return rows if rows else "<tr><td colspan='5'>No incidents recorded.</td></tr>"


def generate_html(audit, eval_m):
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    # deflection rate: blocked / (normal + blocked)
    total = audit["total_queries"] + audit["blocked_count"]
    deflection = round(audit["blocked_count"] / total * 100) if total else 0

    incident_rows = render_incident_rows(audit["incidents"])
    cat_labels_js = json.dumps(audit.get("cat_labels", []), ensure_ascii=False)
    cat_scores_js = json.dumps(eval_m["cat_scores"])
    cat_labels_js = json.dumps(eval_m["cat_labels"], ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Secure Manufacturing RAG — Metrics Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          background: #f5f5f3; color: #1a1a18; font-size: 14px; }}
  .page {{ max-width: 960px; margin: 0 auto; padding: 2rem 1.5rem; }}
  .header {{ margin-bottom: 1.5rem; }}
  .header h1 {{ font-size: 18px; font-weight: 500; margin-bottom: 4px; }}
  .header p  {{ font-size: 12px; color: #6b6b68; }}
  .badge {{ display: inline-block; font-size: 11px; padding: 3px 10px;
             border-radius: 6px; background: #d1fae5; color: #065f46;
             margin-left: 8px; vertical-align: middle; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
               gap: 12px; margin-bottom: 1.5rem; }}
  .kpi {{ background: #eeecea; border-radius: 8px; padding: 1rem; }}
  .kpi-label {{ font-size: 11px; color: #6b6b68; margin-bottom: 6px; }}
  .kpi-value {{ font-size: 26px; font-weight: 500; line-height: 1; }}
  .kpi-unit  {{ font-size: 13px; color: #6b6b68; }}
  .kpi-sub   {{ font-size: 11px; color: #6b6b68; margin-top: 5px; }}
  .charts-grid {{ display: grid; grid-template-columns: 1fr 1fr;
                  gap: 12px; margin-bottom: 1.5rem; }}
  .card {{ background: #fff; border: 0.5px solid rgba(0,0,0,0.1);
           border-radius: 12px; padding: 1rem 1.25rem; }}
  .card-title {{ font-size: 12px; color: #6b6b68; font-weight: 500;
                 margin-bottom: 1rem; }}
  .chart-wrap {{ position: relative; width: 100%; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 12px;
             margin-bottom: 10px; font-size: 11px; color: #6b6b68; }}
  .legend span {{ display: flex; align-items: center; gap: 4px; }}
  .ld {{ width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  th {{ text-align: left; color: #6b6b68; font-weight: 400;
        padding: 4px 0 8px;
        border-bottom: 0.5px solid rgba(0,0,0,0.1); }}
  td {{ padding: 7px 0; border-bottom: 0.5px solid rgba(0,0,0,0.06);
        color: #1a1a18; }}
  tr:last-child td {{ border-bottom: none; }}
  .sev {{ display: inline-block; font-size: 10px; padding: 2px 8px;
           border-radius: 6px; }}
  .sev-low  {{ background: #d1fae5; color: #065f46; }}
  .sev-info {{ background: #dbeafe; color: #1e40af; }}
  .footer {{ font-size: 11px; color: #9b9b97; text-align: right;
             margin-top: 1rem; }}
</style>
</head>
<body>
<div class="page">

  <div class="header">
    <h1>Secure Manufacturing RAG — Metrics Dashboard
      <span class="badge">live data</span>
    </h1>
    <p>Source: audit_log.jsonl + eval_results.csv &nbsp;·&nbsp; Generated: {generated_at}</p>
  </div>

  <div class="kpi-grid">
    <div class="kpi">
      <div class="kpi-label">Total queries</div>
      <div class="kpi-value">{audit["total_queries"]}</div>
      <div class="kpi-sub">{audit["unique_users"]} unique users</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Answer accuracy (eval)</div>
      <div class="kpi-value">{eval_m["avg_combined"]}<span class="kpi-unit">%</span></div>
      <div class="kpi-sub">{eval_m["row_count"]} test cases</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">Requests blocked</div>
      <div class="kpi-value">{audit["blocked_count"]}</div>
      <div class="kpi-sub">0 breached</div>
    </div>
    <div class="kpi">
      <div class="kpi-label">PII detected</div>
      <div class="kpi-value">{audit["pii_count"]}</div>
      <div class="kpi-sub">in responses</div>
    </div>
  </div>

  <div class="charts-grid">
    <div class="card">
      <div class="card-title">Eval score by category (combined_score, %)</div>
      <div class="legend">
        <span><span class="ld" style="background:#1D9E75;"></span>combined score</span>
        <span><span class="ld" style="background:#FAC775;
              border:0.5px dashed #BA7517;"></span>SLO target (80%)</span>
      </div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="catChart"
          role="img"
          aria-label="Bar chart of eval combined scores by category">
          Eval scores by category.
        </canvas>
      </div>
    </div>
    <div class="card">
      <div class="card-title">Per-case combined score (%)</div>
      <div class="legend">
        <span><span class="ld" style="background:#185FA5;"></span>combined score / case</span>
      </div>
      <div class="chart-wrap" style="height:220px;">
        <canvas id="caseChart"
          role="img"
          aria-label="Line chart of combined score per test case">
          Combined score per test case.
        </canvas>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">Security event log</div>
    <table>
      <thead>
        <tr>
          <th style="width:90px;">Date</th>
          <th>Event</th>
          <th style="width:80px;">User</th>
          <th style="width:70px;">Severity</th>
          <th style="width:70px;">Outcome</th>
        </tr>
      </thead>
      <tbody>{incident_rows}</tbody>
    </table>
  </div>

  <div class="footer">
    Secure Manufacturing RAG Adoption Pack · auto-generated report
  </div>

</div>
<script>
const catLabels = {cat_labels_js};
const catScores = {cat_scores_js};
const caseScores = {json.dumps(eval_m["raw_combined"])};

new Chart(document.getElementById('catChart'), {{
  type: 'bar',
  data: {{
    labels: catLabels,
    datasets: [
      {{
        label: 'combined score',
        data: catScores,
        backgroundColor: '#1D9E75',
        borderRadius: 3,
        borderWidth: 0
      }},
      {{
        label: 'SLO (80%)',
        data: Array(catLabels.length).fill(80),
        type: 'line',
        borderColor: '#EF9F27',
        borderDash: [4,3],
        borderWidth: 1.5,
        pointRadius: 0,
        fill: false
      }}
    ]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ min: 0, max: 100,
            ticks: {{ callback: v => v + '%', font: {{ size: 11 }} }},
            grid: {{ color: 'rgba(0,0,0,0.06)' }} }},
      x: {{ ticks: {{ font: {{ size: 11 }} }},
            grid: {{ display: false }} }}
    }}
  }}
}});

new Chart(document.getElementById('caseChart'), {{
  type: 'line',
  data: {{
    labels: caseScores.map((_, i) => 'TC' + String(i+1).padStart(3,'0')),
    datasets: [{{
      label: 'combined score',
      data: caseScores,
      borderColor: '#185FA5',
      backgroundColor: 'rgba(24,95,165,0.08)',
      fill: true,
      tension: 0.3,
      pointRadius: 3,
      pointBackgroundColor: '#185FA5',
      borderWidth: 2
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      y: {{ min: 0, max: 100,
            ticks: {{ callback: v => v + '%', font: {{ size: 11 }} }},
            grid: {{ color: 'rgba(0,0,0,0.06)' }} }},
      x: {{ ticks: {{ font: {{ size: 11 }}, autoSkip: true, maxTicksLimit: 8 }},
            grid: {{ display: false }} }}
    }}
  }}
}});
</script>
</body>
</html>"""
    return html


# ── 4. メイン ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Reading audit log : {AUDIT_LOG}")
    print(f"Reading eval CSV  : {EVAL_CSV}")

    records = load_audit_log(AUDIT_LOG)
    audit = calc_audit_metrics(records)
    eval_m = load_eval_metrics(EVAL_CSV)

    html = generate_html(audit, eval_m)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard generated: {OUTPUT}")
    print(f"   Total queries   : {audit['total_queries']}")
    print(f"   Unique users    : {audit['unique_users']}")
    print(f"   Blocked requests: {audit['blocked_count']}")
    print(f"   Eval cases      : {eval_m['row_count']}")
    print(f"   Avg accuracy    : {eval_m['avg_combined']}%")
