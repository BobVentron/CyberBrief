"""
scraper.py — Collecte RSS + NVD API
Détecte automatiquement le mode hebdo (samedi) vs quotidien
Tague les articles : is_france / is_breach
"""

import feedparser
import requests
import time
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup
from scraper.sources import RSS_FEEDS, CVE_MIN_CVSS, CVE_MAX_COUNT, FRANCE_KEYWORDS


def is_weekly_mode() -> bool:
    """True si on est samedi → récap 7 jours."""
    return datetime.now().weekday() == 5  # 0=lundi … 5=samedi


def get_cutoff(weekly: bool = False) -> datetime:
    """Timestamp de il y a 24h, ou 7 jours en mode hebdo."""
    hours = 24 * 7 if weekly else 24
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def clean_html(raw: str) -> str:
    """Supprime le HTML et tronque à 600 chars."""
    if not raw:
        return ""
    return BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True)[:600]


def is_france_related(title: str, summary: str, source_tags: list) -> bool:
    """Détecte si un article concerne une entité française."""
    if "france" in source_tags:
        return True
    text = (title + " " + summary).lower()
    return any(kw in text for kw in FRANCE_KEYWORDS)


def is_breach_related(title: str, summary: str, source_tags: list) -> bool:
    """Détecte si un article concerne une fuite/piratage/breach."""
    if any(t in source_tags for t in ["breach", "leak", "fuite", "ransomware", "victime", "revendication"]):
        return True
    text = (title + " " + summary).lower()
    keywords = [
        "breach", "leak", "fuite", "pirat", "hack", "compromis", "volé",
        "données personnelles", "data breach", "ransomware", "chiffré",
        "revendiq", "victime", "stolen", "exposed", "dumped", "database",
        "million records", "credentials", "pwned", "dark web", "darkweb",
        "infostealer", "stealer", "combolist", "extorsion",
    ]
    return any(kw in text for kw in keywords)


def scrape_rss(weekly: bool = False) -> list[dict]:
    """Scrape tous les flux RSS et retourne les articles de la période."""
    cutoff = get_cutoff(weekly)
    articles = []

    health = []

    for source in RSS_FEEDS:
        try:
            feed = feedparser.parse(source["url"])

            if feed.bozo and not feed.entries:
                raise Exception(f"flux invalide ou inaccessible ({feed.bozo_exception})")

            count_before = len(articles)

            for entry in feed.entries:
                pub_date = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                    pub_date = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                if pub_date and pub_date < cutoff:
                    continue

                summary = ""
                if hasattr(entry, "summary"):
                    summary = clean_html(entry.summary)
                elif hasattr(entry, "content"):
                    summary = clean_html(entry.content[0].value)

                title = entry.get("title", "Sans titre").strip()

                articles.append({
                    "source":     source["name"],
                    "lang":       source["lang"],
                    "tags":       source["tags"],
                    "title":      title,
                    "url":        entry.get("link", ""),
                    "summary":    summary,
                    "date":       pub_date.strftime("%Y-%m-%d %H:%M") if pub_date else "N/A",
                    "is_france":  is_france_related(title, summary, source["tags"]),
                    "is_breach":  is_breach_related(title, summary, source["tags"]),
                })

            added = len(articles) - count_before
            health.append({"name": source["name"], "url": source["url"],
                           "status": "ok", "articles": added})
            print(f"[RSS] OK {source['name']} ({added} articles)")

        except Exception as e:
            err_msg = str(e)[:100]
            health.append({"name": source["name"], "url": source["url"],
                           "status": "error", "articles": 0, "error": err_msg})
            print(f"[WARN] KO {source['name']}: {e}")

    ok  = [h for h in health if h["status"] == "ok"]
    err = [h for h in health if h["status"] == "error"]
    print(f"[RSS] Sources OK ({len(ok)}/{len(RSS_FEEDS)}) — KO: {[h['name'] for h in err] or 'aucune'}")

    # Tri : FR+breach > FR > breach > autres
    def sort_key(a):
        if a["is_france"] and a["is_breach"]:   return 0
        if a["is_france"]:                        return 1
        if a["is_breach"]:                        return 2
        return 3

    articles.sort(key=sort_key)

    fr_b = sum(1 for a in articles if a["is_france"] and a["is_breach"])
    fr   = sum(1 for a in articles if a["is_france"] and not a["is_breach"])
    b    = sum(1 for a in articles if not a["is_france"] and a["is_breach"])
    print(f"[RSS] {len(articles)} articles — FR+breach:{fr_b} | FR:{fr} | breach:{b}")
    return articles, health


def scrape_nvd_cves(weekly: bool = False) -> list[dict]:
    """Récupère les CVEs High/Critical via l'API NVD."""
    cves = []
    cutoff = get_cutoff(weekly)
    max_cves = CVE_MAX_COUNT * 4 if weekly else CVE_MAX_COUNT

    url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    params = {
        "pubStartDate":   cutoff.strftime("%Y-%m-%dT%H:%M:%S.000"),
        "pubEndDate":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000"),
        "cvssV3Severity": "HIGH",
        "resultsPerPage": 100,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()

        for item in resp.json().get("vulnerabilities", []):
            cve = item.get("cve", {})

            # Score CVSS
            score = None
            metrics = cve.get("metrics", {})
            for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                if key in metrics and metrics[key]:
                    score = metrics[key][0]["cvssData"].get("baseScore")
                    break

            if not score or score < CVE_MIN_CVSS:
                continue

            # Description EN
            desc = next(
                (d["value"] for d in cve.get("descriptions", []) if d["lang"] == "en"),
                "No description"
            )

            # Produits affectés
            affected = []
            for config in cve.get("configurations", []):
                for node in config.get("nodes", []):
                    for cpe in node.get("cpeMatch", []):
                        parts = cpe.get("criteria", "").split(":")
                        if len(parts) > 4:
                            affected.append(f"{parts[3]} {parts[4]}")
            affected = list(set(affected))[:5]

            cves.append({
                "id":          cve.get("id", ""),
                "score":       score,
                "description": desc[:400],
                "affected":    affected,
                "url":         f"https://nvd.nist.gov/vuln/detail/{cve.get('id', '')}",
                "published":   cve.get("published", "")[:10],
            })

        cves.sort(key=lambda x: x["score"] or 0, reverse=True)
        cves = cves[:max_cves]
        print(f"[NVD] {len(cves)} CVEs (CVSS ≥ {CVE_MIN_CVSS})")

    except Exception as e:
        print(f"[WARN] Erreur NVD API: {e}")

    time.sleep(1)  # Respect rate limit NVD
    return cves


def collect_all(weekly: bool = None) -> dict:
    """Point d'entrée — collecte tout et retourne le payload complet.
    Si weekly est None, le mode est auto-détecté (samedi = hebdo)."""
    if weekly is None:
        weekly = is_weekly_mode()
    print(f"[SCRAPER] Mode {'HEBDOMADAIRE' if weekly else 'QUOTIDIEN'} — {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    articles, sources_health = scrape_rss(weekly=weekly)
    cves     = scrape_nvd_cves(weekly=weekly)

    return {
        "articles":       articles,
        "sources_health": sources_health,
        "cves":        cves,
        "mode":        "weekly" if weekly else "daily",
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "period":      "7 derniers jours" if weekly else "dernières 24h",
        "stats": {
            "total_articles": len(articles),
            "breach_fr":      sum(1 for a in articles if a["is_france"] and a["is_breach"]),
            "breach_world":   sum(1 for a in articles if not a["is_france"] and a["is_breach"]),
            "cves":           len(cves),
        },
    }
