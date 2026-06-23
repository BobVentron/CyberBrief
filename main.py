"""
main.py — CyberBrief daemon
Remplace le cron système : APScheduler lit le planning depuis la DB via l'API.
- Polling toutes les 30s : détecte changement de planning et trigger_now
- Le planning est modifiable depuis le panel admin sans redémarrer le container
"""

import os
import sys
import io
import json
import time
import threading
import traceback
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scraper.scraper import collect_all
from briefing.generator import generate_briefing
from notifier.gotify import send_notification

# Config
API_URL                  = os.environ.get("CYBERBRIEF_API_URL", "http://cyberbrief-api:8000")
API_TOKEN                = os.environ.get("INTERNAL_API_TOKEN", "")
TZ                       = os.environ.get("TZ", "Europe/Paris")
DEFAULT_SCHEDULE_DAILY   = "0 21 * * 1-5"   # Lun-Ven 21h
DEFAULT_SCHEDULE_WEEKLY  = "0 21 * * 6"     # Samedi 21h

_brief_lock    = threading.Lock()
_brief_running = False


# Helpers API settings
def get_setting(key: str, default: str = "") -> str:
    try:
        r = requests.get(
            f"{API_URL}/api/internal/settings/{key}",
            headers={"X-Internal-Token": API_TOKEN},
            timeout=5,
        )
        if r.ok:
            v = r.json().get("value")
            return v if v is not None else default
    except Exception:
        pass
    return default


def set_setting(key: str, value: str) -> None:
    try:
        requests.put(
            f"{API_URL}/api/internal/settings/{key}",
            json={"value": str(value)},
            headers={"X-Internal-Token": API_TOKEN},
            timeout=5,
        )
    except Exception:
        pass


# Job principal
class _Tee(io.TextIOBase):
    """Duplique stdout vers la console ET un buffer pour sauvegarder les logs."""
    def __init__(self, real):
        self._real = real
        self._buf  = []

    def write(self, s):
        self._real.write(s)
        if s.strip():
            ts = datetime.now().strftime("%H:%M:%S")
            self._buf.append(f"[{ts}] {s.rstrip()}")
        return len(s)

    def flush(self):
        self._real.flush()

    def getvalue(self) -> str:
        return "\n".join(self._buf[-200:])   # dernières 200 lignes max


def run_brief(weekly: bool = None) -> None:
    """Lance la génération. weekly=None → auto-détection, True → récap, False → daily."""
    global _brief_running
    with _brief_lock:
        if _brief_running:
            print("[DAEMON] Job déjà en cours — ignoré")
            return
        _brief_running = True

    tee = _Tee(sys.stdout)
    sys.stdout = tee

    print(f"\n{'='*52}")
    print(f"  CyberBrief — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*52}\n")

    set_setting("last_run_at",     datetime.now().isoformat())
    set_setting("last_run_status", "running")
    set_setting("last_run_log",    "")

    try:
        # 1. Collecte
        data = collect_all(weekly=weekly)

        # Sauvegarder santé des sources immédiatement
        if "sources_health" in data:
            set_setting("last_sources_health", json.dumps(data["sources_health"], ensure_ascii=False))

        if not data["articles"] and not data["cves"]:
            print("[WARN] Aucune donnée collectée — arrêt.")
            set_setting("last_run_status", "warning: aucune donnée")
            return

        set_setting("last_run_articles", str(data["stats"]["total_articles"]))
        set_setting("last_run_cves",     str(len(data["cves"])))

        # 2. Modèle Claude (depuis DB ou env)
        claude_model = get_setting("claude_model", os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"))

        # 3. Génération rapport
        briefing_html, usage, model_used = generate_briefing(data, model=claude_model)

        # 4. Sauvegarde + mail + Gotify
        send_notification(briefing_html, data, usage=usage, model=model_used)

        set_setting("last_run_status", "success")
        print("\n✅ CyberBrief terminé avec succès.\n")

    except Exception as e:
        msg = str(e)[:120]
        print(f"\nErreur : {e}")
        traceback.print_exc()
        set_setting("last_run_status", f"error: {msg}")

    finally:
        sys.stdout = tee._real
        set_setting("last_run_log", tee.getvalue())
        with _brief_lock:
            _brief_running = False


# Scheduler
scheduler            = BackgroundScheduler(timezone=TZ)
_current_cron_daily  = None
_current_cron_weekly = None


def _update_job(job_id: str, cron_expr: str, weekly: bool) -> None:
    """Met à jour (ou crée) un job APScheduler."""
    try:
        trigger = CronTrigger.from_crontab(cron_expr, timezone=TZ)
        fn = lambda w=weekly: run_brief(weekly=w)   # noqa: E731
        if scheduler.get_job(job_id):
            scheduler.reschedule_job(job_id, trigger=trigger)
        else:
            scheduler.add_job(fn, trigger=trigger, id=job_id, replace_existing=True)
        print(f"[SCHEDULER] {job_id} → {cron_expr}")
    except Exception as e:
        print(f"[SCHEDULER] Expression invalide '{cron_expr}': {e}")


def _refresh_next_run() -> None:
    """Sauvegarde le prochain run_time dans la DB (prend le plus proche des deux jobs)."""
    times = []
    for jid in ("brief-daily", "brief-weekly"):
        job = scheduler.get_job(jid)
        try:
            if job and job.next_run_time:
                times.append(job.next_run_time)
        except AttributeError:
            pass
    if times:
        set_setting("next_run", min(times).isoformat())


def _poll_config() -> None:
    """Vérifie toutes les 30s si les plannings ont changé ou si un trigger est demandé."""
    global _current_cron_daily, _current_cron_weekly

    # Trigger immédiat ?
    if get_setting("trigger_now", "false") == "true":
        set_setting("trigger_now", "false")
        print("[DAEMON] Déclenchement immédiat demandé depuis l'admin")
        threading.Thread(target=run_brief, daemon=True, name="brief-trigger").start()
        return

    # Planning quotidien
    daily = get_setting("cron_schedule_daily", DEFAULT_SCHEDULE_DAILY).strip() or DEFAULT_SCHEDULE_DAILY
    if daily != _current_cron_daily:
        _update_job("brief-daily", daily, weekly=False)
        _current_cron_daily = daily
        _refresh_next_run()

    # Planning hebdomadaire
    weekly = get_setting("cron_schedule_weekly", DEFAULT_SCHEDULE_WEEKLY).strip() or DEFAULT_SCHEDULE_WEEKLY
    if weekly != _current_cron_weekly:
        _update_job("brief-weekly", weekly, weekly=True)
        _current_cron_weekly = weekly
        _refresh_next_run()


# Main
def main() -> None:
    print(f"\n{'='*52}")
    print(f"  CyberBrief Daemon — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Timezone : {TZ}")
    print(f"{'='*52}\n")

    # Attendre que l'API soit disponible (max 150s)
    for attempt in range(30):
        try:
            r = requests.get(f"{API_URL}/api/health", timeout=3)
            if r.ok:
                print("[DAEMON] ✅ API disponible")
                break
        except Exception:
            pass
        print(f"[DAEMON] Attente API… ({attempt + 1}/30)")
        time.sleep(5)
    else:
        print("[DAEMON] ❌ API indisponible après 150s — arrêt")
        sys.exit(1)

    # Plannings initiaux
    _poll_config()

    # Polling de la config toutes les 30s
    scheduler.add_job(_poll_config, "interval", seconds=30, id="poll", replace_existing=True)

    scheduler.start()
    print(f"[DAEMON] Démarré — Daily: {_current_cron_daily} | Weekly: {_current_cron_weekly}")
    print("[DAEMON] En attente… (Ctrl+C pour arrêter)\n")

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown(wait=False)
        print("[DAEMON] Arrêté proprement.")


if __name__ == "__main__":
    main()
