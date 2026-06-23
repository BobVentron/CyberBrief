"""
generator.py — Génère le rapport HTML via Claude API
Deux prompts distincts : quotidien (lun-ven) et hebdomadaire (samedi)
"""

import os
import anthropic
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT QUOTIDIEN
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_DAILY = """Tu es un analyste en cybersécurité senior qui rédige un briefing quotidien personnel.

STYLE : Français, pro, dense. Aller droit au but. 3-5 min de lecture.

STRUCTURE OBLIGATOIRE (dans cet ordre, titres HTML <h2>) :

1. 🔥 INCIDENTS & ATTAQUES DU JOUR
   Incidents actifs, campagnes en cours, nouvelles techniques observées.

2. 🇫🇷 PIRATAGES & FUITES — FRANCE
   OBLIGATOIRE même si peu d'éléments.
   Toutes les entreprises, administrations, hôpitaux, collectivités françaises
   mentionnées dans une fuite, revendication ransomware ou compromission.
   Pour chaque victime : nom · secteur · type de données · volume si connu ·
   groupe revendiquant · lien source.
   Si rien : écrire "Aucun incident confirmé en France sur les dernières 24h."

3. 🌍 PIRATAGES & FUITES — MONDE
   Autres breaches significatifs hors France.
   Même format : entité · données · volume · acteur · source.

4. 🩹 CVEs CRITIQUES DU JOUR
   Focus sur celles exploitées in-the-wild ou avec PoC public.

5. 🛠️ OUTILS & PUBLICATIONS NOTABLES

6. 📌 À SURVEILLER
   2-3 points de vigilance concrets pour les prochaines heures/jours.

RÈGLES DE LIENS :
- Chaque item termine par : <a href="URL_EXACTE" style="color:#0ea5e9;font-size:11px;font-family:monospace;">→ Source (NomSite)</a>
- CVEs : lien NVD obligatoire → https://nvd.nist.gov/vuln/detail/CVE-XXXX
- Ne jamais inventer une URL.

FORMAT : HTML propre SANS balises <html><head><body>. Sections <h2>, sous-titres <h3>.
"""


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT HEBDOMADAIRE
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_WEEKLY = """Tu es un analyste en cybersécurité senior qui rédige le récapitulatif hebdomadaire de veille.

STYLE : Français, analytique, dense. Relier les événements entre eux. Vision semaine.

STRUCTURE OBLIGATOIRE (dans cet ordre, titres HTML <h2>) :

1. 🗓️ SEMAINE EN UN COUP D'ŒIL
   3-5 phrases sur le fil rouge : thème dominant, acteurs, ambiance générale.

2. 🔥 INCIDENTS MAJEURS DE LA SEMAINE
   Incidents significatifs regroupés par thème (vague ransomware, campagne APT...).

3. 🇫🇷 PIRATAGES & FUITES — FRANCE (SEMAINE)
   SECTION PRIORITAIRE ET OBLIGATOIRE.
   Toutes les entités françaises touchées cette semaine.
   Pour chaque victime : nom · secteur · type de données · volume · groupe · date ·
   statut CNIL · lien source.
   Préciser : incident confirmé vs seulement revendiqué.
   Si rien de confirmé : le noter explicitement + éventuelles rumeurs non confirmées.

4. 🌍 PIRATAGES & FUITES — MONDE (TOP 5)
   Les 5 plus significatifs de la semaine.
   Critères : volume, sensibilité des données, notoriété, technique notable.

5. 🩹 TOP CVEs DE LA SEMAINE
   CVEs critiques, focus exploitées in-the-wild ou avec PoC public.

6. 📈 TENDANCES & PATTERNS
   Ce qui monte, ce qui relie les événements, secteurs les plus ciblés.
   Minimum 4 points.

7. 🛠️ OUTILS & PUBLICATIONS NOTABLES
   Outils, write-ups, rapports, guides publiés cette semaine.

8. 📊 STATS DE LA SEMAINE
   Incidents par type · CVEs par sévérité · familles de malware actives ·
   graphique d'activité par jour · breaches FR et monde.

9. 📌 À SURVEILLER LA SEMAINE PROCHAINE
   3-5 points de vigilance concrets pour les 7 prochains jours.

RÈGLES DE LIENS :
- Chaque item a son lien source.
- Format : <a href="URL" style="color:#00d4ff;font-size:11px;font-family:monospace;">→ Source (NomSite)</a>
- CVEs : lien NVD obligatoire.
- Ne jamais inventer une URL.

FORMAT : HTML propre SANS balises <html><head><body>. Sections <h2>, sous-groupes <h3>.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CONSTRUCTION DU PROMPT UTILISATEUR
# ═══════════════════════════════════════════════════════════════════════════

def build_user_prompt(data: dict) -> str:
    articles  = data["articles"]
    cves      = data["cves"]
    mode      = data.get("mode", "daily")
    period    = data.get("period", "dernières 24h")
    date_str  = data["collected_at"]
    stats     = data.get("stats", {})

    lines = []
    label = "RÉCAPITULATIF HEBDOMADAIRE" if mode == "weekly" else "BRIEFING QUOTIDIEN"
    lines.append(f"=== {label} — {date_str} ===")
    lines.append(f"Période : {period}")
    lines.append(f"Total articles : {stats.get('total_articles', len(articles))}")
    lines.append(f"Articles France+breach : {stats.get('breach_fr', 0)}")
    lines.append(f"Articles breach monde : {stats.get('breach_world', 0)}")
    lines.append(f"CVEs (CVSS ≥ 7.0) : {len(cves)}\n")

    # Séparation en catégories
    fr_breach    = [a for a in articles if a.get("is_france") and a.get("is_breach")]
    world_breach = [a for a in articles if not a.get("is_france") and a.get("is_breach")]
    other        = [a for a in articles if not a.get("is_breach")]

    def fmt_articles(lst):
        out = []
        for a in lst:
            out.append(f"[{a['source']}] [{a.get('date','')}] {a['title']}")
            if a.get("summary"):
                out.append(f"  Résumé: {a['summary']}")
            if a.get("url"):
                out.append(f"  URL: {a['url']}")
            out.append("")
        return out

    lines.append(f"=== 🇫🇷 ARTICLES FRANCE + BREACH ({len(fr_breach)}) ===")
    lines.extend(fmt_articles(fr_breach))

    lines.append(f"=== 🌍 ARTICLES BREACH MONDE ({len(world_breach)}) ===")
    lines.extend(fmt_articles(world_breach))

    lines.append(f"=== AUTRES ARTICLES ({len(other)}) ===")
    lines.extend(fmt_articles(other))

    # CVEs
    if cves:
        lines.append(f"=== CVEs HIGH/CRITICAL ({len(cves)}) ===")
        for c in cves:
            affected = ", ".join(c["affected"]) if c["affected"] else "N/A"
            lines.append(f"{c['id']} | CVSS {c['score']} | {c.get('published','')}")
            lines.append(f"  Produits : {affected}")
            lines.append(f"  Description : {c['description']}")
            lines.append(f"  URL : {c['url']}\n")

    lines.append("=== FIN ===")
    if mode == "weekly":
        lines.append("Génère le récapitulatif hebdomadaire HTML complet selon la structure ci-dessus.")
    else:
        lines.append("Génère le briefing quotidien HTML complet selon la structure ci-dessus.")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# GÉNÉRATION
# ═══════════════════════════════════════════════════════════════════════════

def generate_briefing(data: dict, model: str = None) -> tuple[str, dict, str]:
    """
    Retourne (html, usage, model_used)
    usage = {"input_tokens": int, "output_tokens": int}
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    model          = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
    mode           = data.get("mode", "daily")
    system_prompt  = SYSTEM_WEEKLY if mode == "weekly" else SYSTEM_DAILY
    max_tokens     = 8192 if mode == "weekly" else 4096
    label          = "récap hebdo" if mode == "weekly" else "briefing quotidien"

    user_prompt = build_user_prompt(data)
    print(f"[CLAUDE] Génération {label} ({model}) — {len(user_prompt)} chars d'input…")

    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    html  = message.content[0].text
    usage = {
        "input_tokens":  message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }
    print(f"[CLAUDE] {label} généré — {len(html)} chars "
          f"| {usage['input_tokens']:,} in + {usage['output_tokens']:,} out tokens")
    return html, usage, model
