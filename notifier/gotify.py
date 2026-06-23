"""
notifier/gotify.py v2 — Sauvegarde rapport, log usage API, déclenche mail, notif Gotify
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# SAUVEGARDE RAPPORT
# ═══════════════════════════════════════════════════════════════════════════

def save_report(briefing_html: str, data: dict) -> tuple[str, str, str]:
    mode = data.get("mode", "daily")
    now  = datetime.now()

    if mode == "weekly":
        filename = f"hebdo-{now.strftime('%Y-W%V')}.html"
        title    = f"Récap Hebdo — Semaine {now.strftime('W%V %Y')}"
    else:
        filename = f"daily-{now.strftime('%Y-%m-%d')}.html"
        title    = f"Brief Quotidien — {now.strftime('%d/%m/%Y')}"

    reports_dir = Path(os.environ.get("REPORTS_DIR", "/app/reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)

    full_html = _wrap_report_html(briefing_html, title, mode, now)
    (reports_dir / filename).write_text(full_html, encoding="utf-8")
    print(f"[REPORT] Sauvegardé → {filename}")

    _update_manifest(reports_dir, filename, title, data, mode, now)

    base_url = os.environ.get("REPORT_BASE_URL", "http://localhost:8080")
    return filename, f"{base_url}/reports/{filename}", title


def _wrap_report_html(content: str, title: str, mode: str, now) -> str:
    """Enveloppe le fragment HTML dans une page complète avec CSS dark theme."""
    badge = "🗓️ Récap Hebdo" if mode == "weekly" else "🛡️ Brief Quotidien"
    date_str = now.strftime("%d/%m/%Y")
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — CyberBrief</title>
  <style>
    :root {{
      --bg:#07080a; --surface:#0c0e12; --border:#1c2028; --border-h:#253550;
      --accent:#00d4ff; --text:#9baabf; --text-bright:#e4eaf2; --text-dim:#4a5568;
      --mono:'Courier New',monospace;
    }}
    * {{ box-sizing:border-box; margin:0; padding:0; }}
    body {{ background:var(--bg); color:var(--text); font-family:var(--mono); font-size:13px; line-height:1.7; }}
    a {{ color:#0ea5e9; text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .wrapper {{ max-width:820px; margin:0 auto; padding:32px 20px 60px; }}
    header {{
      display:flex; align-items:baseline; justify-content:space-between;
      padding-bottom:18px; border-bottom:1px solid var(--border); margin-bottom:28px;
    }}
    .logo {{ font-family:Georgia,serif; font-size:22px; font-weight:700; color:var(--text-bright); }}
    .logo span {{ color:var(--accent); }}
    .meta {{ font-size:11px; color:var(--text-dim); }}
    h2 {{
      margin:28px 0 8px; padding:10px 14px;
      background:linear-gradient(90deg,#0d1929 0%,var(--surface) 100%);
      border-left:3px solid var(--accent); color:var(--accent);
      font-size:13px; font-weight:700; letter-spacing:.05em;
    }}
    h3 {{ margin:18px 0 5px; color:var(--text-bright); font-size:13px; font-weight:600; }}
    p {{ margin:5px 0 8px; }}
    ul {{ margin:5px 0 8px; padding-left:18px; }}
    li {{ margin:4px 0; }}
    strong {{ color:var(--text-bright); }}
    hr {{ border:none; border-top:1px solid var(--border); margin:20px 0; }}
    .source-link {{ font-size:11px; }}
    footer {{ margin-top:40px; padding-top:16px; border-top:1px solid var(--border); font-size:10px; color:var(--text-dim); }}
  </style>
</head>
<body>
  <div class="wrapper">
    <header>
      <div class="logo">Cyber<span>Brief</span></div>
      <div class="meta">{badge} &middot; {date_str}</div>
    </header>
    {content}
    <footer>CyberBrief &mdash; Veille cybersécurité automatisée &mdash; {now.strftime('%Y-%m-%d %H:%M')}</footer>
  </div>
</body>
</html>"""


def _update_manifest(reports_dir, filename, title, data, mode, now):
    manifest_path = reports_dir / "manifest.json"
    try:
        existing = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    except Exception:
        existing = []

    stats = data.get("stats", {})
    existing = [r for r in existing if r.get("filename") != filename]
    existing.insert(0, {
        "filename":    filename,
        "title":       title,
        "type":        mode,
        "date":        now.strftime("%A %d %B %Y à %H:%M").capitalize(),
        "articles":    stats.get("total_articles", len(data.get("articles", []))),
        "cves":        len(data.get("cves", [])),
        "breaches_fr": stats.get("breach_fr", 0),
        "period":      data.get("period", ""),
    })
    existing = existing[:30]
    manifest_path.write_text(
        json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[MANIFEST] {len(existing)} rapport(s) indexés")


# ═══════════════════════════════════════════════════════════════════════════
# LOG USAGE API CLAUDE → API CYBERBRIEF
# ═══════════════════════════════════════════════════════════════════════════

def log_api_usage(filename: str, report_type: str, usage: dict, model: str):
    """
    Envoie les stats de tokens à l'API pour tracking des coûts.
    usage dict doit contenir : input_tokens, output_tokens
    """
    api_url   = os.environ.get("CYBERBRIEF_API_URL", "http://cyberbrief-api:8000")
    api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    if not api_token or not usage:
        return

    try:
        resp = requests.post(
            f"{api_url}/api/internal/api-usage",
            json={
                "report_file":   filename,
                "report_type":   report_type,
                "input_tokens":  usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "model_used":    model,
            },
                    headers={"X-Internal-Token": api_token},
            timeout=10,
        )
        if resp.ok:
            d = resp.json()
            print(f"[USAGE] Tokens: {d.get('total_tokens'):,} · Coût: ${d.get('cost_usd', 0):.5f}")
        else:
            print(f"[USAGE] ⚠️  Erreur log usage: {resp.status_code}")
    except Exception as e:
        print(f"[USAGE] ⚠️  {e}")


# ═══════════════════════════════════════════════════════════════════════════
# ENVOI MAIL
# ═══════════════════════════════════════════════════════════════════════════

def trigger_mail_send(filename: str, report_type: str, title: str):
    api_url   = os.environ.get("CYBERBRIEF_API_URL", "http://cyberbrief-api:8000")
    api_token = os.environ.get("INTERNAL_API_TOKEN", "")

    if not api_token:
        print("[MAILER] INTERNAL_API_TOKEN non défini — mail ignoré")
        return

    try:
        resp = requests.post(
            f"{api_url}/api/mailer/send-report",
            json={
                "report_file":  filename,
                "report_type":  report_type,
                "report_title": title,
            },
            headers={"X-Internal-Token": api_token},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        print(f"[MAILER] ✅ {result.get('users_notified', 0)} user(s) notifiés")
        if result.get('users_failed', 0):
            print(f"[MAILER] ⚠️  {result['users_failed']} échec(s)")
    except Exception as e:
        print(f"[MAILER] ⚠️  Erreur: {e}")


# ═══════════════════════════════════════════════════════════════════════════
# NOTIFICATION GOTIFY
# ═══════════════════════════════════════════════════════════════════════════

def send_notification(briefing_html: str, data: dict, usage: dict = None, model: str = "claude-sonnet-4-5") -> None:
    """
    Flux principal :
    1. Sauvegarde rapport
    2. Log usage Claude API
    3. Envoi mail aux users
    4. Push Gotify
    """
    mode  = data.get("mode", "daily")
    stats = data.get("stats", {})
    now   = datetime.now()

    # 1. Sauvegarde
    filename, report_url, title = save_report(briefing_html, data)

    # 2. Log coûts API (non-bloquant)
    if usage:
        log_api_usage(filename, mode, usage, model)

    # 3. Envoi mail (non-bloquant)
    trigger_mail_send(filename, mode, title)

    # 4. Gotify push
    gotify_url   = os.environ.get("GOTIFY_URL", "")
    gotify_token = os.environ.get("GOTIFY_APP_TOKEN", "")

    if not gotify_url or not gotify_token:
        print("[GOTIFY] Non configuré — notification ignorée")
        return

    notif_title = f"🗓️ CyberBrief Hebdo — W{now.strftime('%V')}" \
                  if mode == "weekly" else f"🛡️ CyberBrief — {now.strftime('%d/%m/%Y')}"
    priority    = 7 if mode == "weekly" else 5

    breaches_fr    = stats.get("breach_fr", 0)
    breaches_world = stats.get("breach_world", 0)
    cves_count     = len(data.get("cves", []))
    articles_count = stats.get("total_articles", 0)

    fr_line = f"🇫🇷 **{breaches_fr} incident(s) France**" if breaches_fr > 0 \
              else "🇫🇷 Aucun incident France confirmé"

    cost_line = ""
    if usage:
        total_tok = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        pricing   = {
            "claude-sonnet-4-6": (3, 15),
            "claude-opus-4-8":   (15, 75),
            "claude-haiku-4-5-20251001": (0.8, 4),
            # anciennes références
            "claude-sonnet-4-5": (3, 15),
            "claude-opus-4-5":   (15, 75),
        }
        rates     = pricing.get(model, (3, 15))
        cost      = (usage.get("input_tokens", 0) * rates[0] + usage.get("output_tokens", 0) * rates[1]) / 1_000_000
        cost_line = f"\n💰 {total_tok:,} tokens · ${cost:.5f}"

    message = (
        f"{fr_line}\n"
        f"🌍 {breaches_world} breach(es)  ·  "
        f"🩹 {cves_count} CVEs  ·  "
        f"📰 {articles_count} articles"
        f"{cost_line}\n\n"
        f"[→ Lire le rapport]({report_url})"
    )

    try:
        resp = requests.post(
            f"{gotify_url.rstrip('/')}/message",
            json={
                "title":    notif_title,
                "message":  message,
                "priority": priority,
                "extras": {
                    "client::notification": {"click": {"url": report_url}},
                    "client::display":      {"contentType": "text/markdown"},
                },
            },
            headers={"X-Gotify-Key": gotify_token},
            timeout=10,
        )
        resp.raise_for_status()
        print(f"[GOTIFY] ✅ Push envoyé")
    except Exception as e:
        print(f"[GOTIFY] ⚠️  {e}")
