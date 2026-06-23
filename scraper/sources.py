# sources.py — Toutes les sources de veille cyber

RSS_FEEDS = [
    # ═══════════════════════════════════════════════════
    # FRANÇAIS
    # ═══════════════════════════════════════════════════
    {
        "name": "IT-Connect",
        "url": "https://www.it-connect.fr/feed/",
        "lang": "fr",
        "tags": ["actu", "sécurité"]
    },
    {
        "name": "CERT-FR Alertes",
        "url": "https://www.cert.ssi.gouv.fr/alerte/feed/",
        "lang": "fr",
        "tags": ["alerte", "officiel"]
    },
    {
        "name": "CERT-FR Avis",
        "url": "https://www.cert.ssi.gouv.fr/avis/feed/",
        "lang": "fr",
        "tags": ["avis", "officiel"]
    },
    {
        "name": "ANSSI / cyber.gouv.fr",
        "url": "https://cyber.gouv.fr/actualites/rss/",
        "lang": "fr",
        "tags": ["officiel", "gouvernement"]
    },
    {
        "name": "Zataz",
        "url": "https://www.zataz.com/feed/",
        "lang": "fr",
        "tags": ["incident", "fuite", "breach", "france"]
        # Référence FR pour fuites/piratages d'entités françaises
    },
    {
        "name": "Silicon.fr",
        "url": "https://www.silicon.fr/feed/",
        "lang": "fr",
        "tags": ["actu", "entreprise", "france"]
    },
    {
        "name": "01net Sécurité",
        "url": "https://www.01net.com/actualites/securite/feed/",
        "lang": "fr",
        "tags": ["actu", "france"]
    },
    {
        "name": "Korben",
        "url": "https://korben.info/feed",
        "lang": "fr",
        "tags": ["outil", "actu", "technique"]
    },

    # ═══════════════════════════════════════════════════
    # BREACH / LEAK TRACKING (MONDIAL + FR)
    # ═══════════════════════════════════════════════════
    {
        "name": "Ransomware.live",
        "url": "https://www.ransomware.live/feed.xml",
        "lang": "en",
        "tags": ["ransomware", "victime", "revendication", "breach", "france"]
        # Tracker temps réel des victimes revendiquées par les groupes ransomware
        # Couvre toutes les entités françaises revendiquées
    },
    {
        "name": "DataBreaches.net",
        "url": "https://www.databreaches.net/feed/",
        "lang": "en",
        "tags": ["breach", "leak", "données", "france"]
        # Blog dédié 100% aux fuites de données — très complet, couvre le FR
    },
    {
        "name": "Have I Been Pwned",
        "url": "https://feeds.feedburner.com/HaveIBeenPwnedLatestBreaches",
        "lang": "en",
        "tags": ["breach", "leak", "données"]
        # Référence mondiale — toutes les nouvelles bases leakées indexées
    },
    {
        "name": "Bleeping Computer — Data Breach",
        "url": "https://www.bleepingcomputer.com/feed/?cat=data-breach",
        "lang": "en",
        "tags": ["breach", "leak"]
    },
    {
        "name": "Privacy Affairs",
        "url": "https://www.privacyaffairs.com/feed/",
        "lang": "en",
        "tags": ["breach", "darkweb", "données"]
    },
    {
        "name": "Hudson Rock",
        "url": "https://hudsonrock.substack.com/feed",
        "lang": "en",
        "tags": ["infostealer", "credentials", "breach", "france"]
        # Spécialisé infostealers + credentials volés — trace les credentials FR
    },
    {
        "name": "Flashpoint Blog",
        "url": "https://flashpoint.io/blog/feed/",
        "lang": "en",
        "tags": ["darkweb", "threat intel", "breach", "credentials"]
    },

    # ═══════════════════════════════════════════════════
    # INTERNATIONAL — ACTU GÉNÉRALE
    # ═══════════════════════════════════════════════════
    {
        "name": "The Hacker News",
        "url": "https://thehackernews.com/feeds/posts/default",
        "lang": "en",
        "tags": ["incident", "CVE", "malware"]
    },
    {
        "name": "Bleeping Computer",
        "url": "https://www.bleepingcomputer.com/feed/",
        "lang": "en",
        "tags": ["incident", "ransomware", "outil"]
    },
    {
        "name": "Krebs on Security",
        "url": "https://krebsonsecurity.com/feed/",
        "lang": "en",
        "tags": ["investigation", "cybercriminalité", "breach"]
    },
    {
        "name": "Dark Reading",
        "url": "https://www.darkreading.com/rss.xml",
        "lang": "en",
        "tags": ["actu", "entreprise", "threat intel"]
    },
    {
        "name": "Schneier on Security",
        "url": "https://www.schneier.com/feed/atom/",
        "lang": "en",
        "tags": ["analyse", "opinion", "politique"]
    },
    {
        "name": "SANS Internet Stormcast",
        "url": "https://isc.sans.edu/rssfeed_full.xml",
        "lang": "en",
        "tags": ["technique", "analyse"]
    },
    {
        "name": "Recorded Future",
        "url": "https://www.recordedfuture.com/feed",
        "lang": "en",
        "tags": ["threat intel", "APT", "analyse"]
    },
    {
        "name": "Cisco Talos Intelligence",
        "url": "https://blog.talosintelligence.com/rss/",
        "lang": "en",
        "tags": ["threat intel", "APT", "malware"]
    },
    {
        "name": "Palo Alto Unit 42",
        "url": "https://unit42.paloaltonetworks.com/feed/",
        "lang": "en",
        "tags": ["threat intel", "APT", "breach"]
    },
]

# ═══════════════════════════════════════════════════
# PARAMÈTRES CVE
# ═══════════════════════════════════════════════════
CVE_MIN_CVSS = 7.0   # CVSS minimum pour inclure une CVE (7.0 = High)
CVE_MAX_COUNT = 20   # Nombre max de CVEs par rapport (×4 en mode hebdo)

# ═══════════════════════════════════════════════════
# MOTS-CLÉS FRANCE
# ═══════════════════════════════════════════════════
# Utilisés par le scraper pour détecter automatiquement les articles
# concernant des entités françaises (boost de priorité dans le prompt)
FRANCE_KEYWORDS = [
    "france", "français", "française", "paris", "lyon", "marseille",
    "bordeaux", "toulouse", "nantes", "strasbourg", "lille", "rennes",
    ".fr", "sncf", "edf", "orange", "sfr", "bouygues", "société générale",
    "bnp", "crédit agricole", "axa", "total", "renault", "psa", "airbus",
    "mairie", "préfecture", "hôpital", "chu", "ap-hp", "caf", "ameli",
    "impots.gouv", "france travail", "pole emploi", "ministère",
    "collectivité", "région", "département", "commune",
    "french", "hexagone", "leclerc", "carrefour", "decathlon",
    "free", "numericable", "la poste", "cnav", "urssaf",
    "thales", "safran", "dassault", "legrand", "schneider"
]
