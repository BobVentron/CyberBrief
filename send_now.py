"""
send_now.py — Génère un rapport CyberBrief et l'envoie par email
Sans Docker, sans Node.js — exécution directe Python
"""

import os, sys, smtplib, traceback
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Configuration (depuis .env)
from dotenv import load_dotenv
load_dotenv()

# Mapping des variables (supporte les deux conventions de nommage)
os.environ.setdefault("ANTHROPIC_API_KEY",
    os.environ.get("ANTHROPIC_API_KEY", ""))
os.environ.setdefault("SMTP_PASSWORD",
    os.environ.get("SMTP_PASS", ""))
os.environ.setdefault("REPORT_BASE_URL",
    os.environ.get("APP_URL", "http://localhost:8080"))

RECIPIENT = "bastien222004@outlook.fr"

SMTP_HOST = os.environ.get("SMTP_HOST", "ssl0.ovh.net")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASSWORD") or os.environ.get("SMTP_PASS", "")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)

def send_email(subject: str, html_body: str, filename: str):
    print(f"\n[EMAIL] Envoi vers {RECIPIENT}...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"CyberBrief <{SMTP_FROM}>"
    msg["To"]      = RECIPIENT

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_FROM, [RECIPIENT], msg.as_string())

    print(f"[EMAIL] ✅ Envoyé à {RECIPIENT}")

def main():
    print(f"\n{'='*55}")
    print(f"  CyberBrief — Génération & Envoi direct")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*55}\n")

    # 1. Collecte RSS + NVD
    print("[1/3] Scraping des sources...")
    from scraper.scraper import collect_all
    data = collect_all()

    if not data["articles"] and not data["cves"]:
        print("❌ Aucune donnée collectée.")
        sys.exit(1)

    print(f"      ✅ {data['stats']['total_articles']} articles, {len(data['cves'])} CVEs")

    # 2. Génération Claude
    print(f"\n[2/3] Génération du rapport via Claude...")
    from briefing.generator import generate_briefing
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    html, usage, model_used = generate_briefing(data, model=model)
    print(f"      ✅ {len(html):,} chars | {usage['input_tokens']:,} in + {usage['output_tokens']:,} out tokens")

    # 3. Sauvegarde locale
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    mode = data.get("mode", "daily")
    now  = datetime.now()
    filename = f"hebdo-{now.strftime('%Y-W%V')}.html" if mode == "weekly" \
               else f"daily-{now.strftime('%Y-%m-%d')}.html"
    (reports_dir / filename).write_text(html, encoding="utf-8")
    print(f"      ✅ Sauvegardé → reports/{filename}")

    # 4. Envoi email
    print(f"\n[3/3] Envoi email...")
    date_str   = now.strftime("%d/%m/%Y")
    is_weekly  = mode == "weekly"
    badge_text = "Récap Hebdo" if is_weekly else "Brief Quotidien"
    badge_icon = "🗓️" if is_weekly else "🛡️"
    report_url = f"{os.environ.get('REPORT_BASE_URL','https://cyberbrief.soleilhac.me')}/reports/{filename}"

    n_articles = data["stats"]["total_articles"]
    n_cves     = len(data["cves"])
    n_breach   = data["stats"].get("breach_fr", 0) + data["stats"].get("breach_world", 0)

    # Inline styles
    styled = (html
        .replace("<h2>",
            '<h2 style="margin:28px 0 8px;padding:10px 14px;'
            'background:linear-gradient(90deg,#0d1929 0%,#0c0e12 100%);'
            'border-left:3px solid #00d4ff;color:#00d4ff;font-size:13px;'
            'font-family:\'Courier New\',monospace;font-weight:700;letter-spacing:.05em;">')
        .replace("<h3>",
            '<h3 style="margin:18px 0 5px;color:#e4eaf2;font-size:13px;'
            'font-family:\'Courier New\',monospace;font-weight:600;">')
        .replace("<p>",
            '<p style="margin:5px 0 8px;line-height:1.7;font-size:13px;color:#9baabf;">')
        .replace("<ul>",
            '<ul style="margin:5px 0 8px;padding-left:18px;color:#9baabf;">')
        .replace("<li>",
            '<li style="margin:4px 0;font-size:13px;line-height:1.6;">')
        .replace("<hr>",
            '<hr style="border:none;border-top:1px solid #1a2035;margin:20px 0;">')
        .replace("<strong>",
            '<strong style="color:#e4eaf2;">')
    )

    # Stat badges
    def stat_badge(val, label, color="#253550"):
        return (
            f'<td align="center" style="padding:0 6px;">'
            f'<span style="display:inline-block;background:{color};border:1px solid #1c2845;'
            f'border-radius:4px;padding:5px 12px;font-size:11px;font-family:\'Courier New\',monospace;'
            f'color:#b8c4d0;white-space:nowrap;">'
            f'<span style="color:#00d4ff;font-weight:700;">{val}</span>&nbsp;{label}'
            f'</span></td>'
        )

    stat_row = (
        stat_badge(n_articles, "articles") +
        stat_badge(n_cves, "CVEs", "#1a1225") +
        stat_badge(n_breach, "incidents/fuites", "#1a1510")
    )

    email_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
</head>
<body style="margin:0;padding:0;background:#07080a;font-family:Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#07080a;">
<tr><td align="center" style="padding:28px 12px 40px;">

  <!-- Card -->
  <table width="640" cellpadding="0" cellspacing="0"
         style="background:#0c0e12;border:1px solid #1c2028;border-radius:6px;max-width:640px;">

    <!-- Header -->
    <tr>
      <td style="padding:22px 28px;border-bottom:1px solid #1c2028;background:#0a0c10;border-radius:6px 6px 0 0;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <span style="font-family:Georgia,serif;font-size:22px;font-weight:700;color:#eef2f7;letter-spacing:-.3px;">
                Cyber<span style="color:#00d4ff;">Brief</span>
              </span>
              <span style="display:inline-block;margin-left:10px;vertical-align:middle;
                    font-size:10px;font-family:\'Courier New\',monospace;color:#4a6080;
                    background:#0d1520;border:1px solid #1c2845;border-radius:3px;
                    padding:2px 7px;letter-spacing:.06em;text-transform:uppercase;">
                Veille Cyber
              </span>
            </td>
            <td align="right">
              <span style="font-size:11px;font-family:\'Courier New\',monospace;color:#4a6080;">
                {badge_icon}&nbsp;{badge_text}&nbsp;&nbsp;·&nbsp;&nbsp;{date_str}
              </span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

    <!-- Stats bar -->
    <tr>
      <td style="padding:14px 28px;background:#09111e;border-bottom:1px solid #1c2028;">
        <table cellpadding="0" cellspacing="0">
          <tr>{stat_row}</tr>
        </table>
      </td>
    </tr>

    <!-- Body -->
    <tr>
      <td style="padding:24px 28px 20px;color:#9baabf;font-size:13px;line-height:1.7;">
        {styled}
      </td>
    </tr>

    <!-- CTA -->
    <tr>
      <td align="center" style="padding:20px 28px 28px;border-top:1px solid #1c2028;">
        <a href="{report_url}"
           style="display:inline-block;background:#00d4ff;color:#07080a;
                  font-family:\'Courier New\',monospace;font-size:12px;font-weight:700;
                  text-decoration:none;padding:11px 28px;border-radius:4px;
                  letter-spacing:.06em;text-transform:uppercase;">
          Voir le rapport complet &rarr;
        </a>
        <p style="margin:12px 0 0;font-size:10px;color:#2d3748;font-family:\'Courier New\',monospace;">
          <a href="{os.environ.get('REPORT_BASE_URL','https://cyberbrief.soleilhac.me')}"
             style="color:#2d5080;text-decoration:none;">cyberbrief.soleilhac.me</a>
        </p>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="padding:14px 28px;background:#080a0d;border-top:1px solid #131820;border-radius:0 0 6px 6px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td>
              <span style="font-size:10px;color:#232d3a;font-family:\'Courier New\',monospace;">
                CyberBrief &mdash; Veille cybersécurité automatisée &mdash; {model_used}
              </span>
            </td>
            <td align="right">
              <span style="font-size:10px;color:#232d3a;font-family:\'Courier New\',monospace;">
                {now.strftime('%H:%M')} UTC+2
              </span>
            </td>
          </tr>
        </table>
      </td>
    </tr>

  </table>
</td></tr>
</table>
</body>
</html>"""

    subject = f"[CyberBrief] {badge_icon} {badge_text} — {date_str}"
    send_email(subject, email_html, filename)

    # Résumé
    cost = (usage["input_tokens"] * 3 + usage["output_tokens"] * 15) / 1_000_000
    print(f"\n{'='*55}")
    print(f"✅ TERMINÉ")
    print(f"   📊 {data['stats']['total_articles']} articles · {len(data['cves'])} CVEs")
    print(f"   🤖 Modèle : {model_used}")
    print(f"   💰 Coût estimé : ${cost:.5f}")
    print(f"   📬 Email envoyé à : {RECIPIENT}")
    print(f"   📄 Rapport : reports/{filename}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        traceback.print_exc()
        sys.exit(1)
