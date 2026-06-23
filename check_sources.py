import requests, feedparser

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def test_feed(name, url):
    r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
    ct = r.headers.get("Content-Type", "")
    feed = feedparser.parse(r.text)
    n = len(feed.entries)
    status = "OK" if n > 0 else "VIDE"
    if feed.bozo and n == 0:
        status = f"BOZO ({feed.bozo_exception})"
    print(f"[{status}] {name} ({n} entries) — {url}")
    if n > 0:
        print(f"       Ex: {feed.entries[0].get('title','?')[:70]}")

# Confirmed feeds to validate
print("=== ANSSI ===")
test_feed("cyber.gouv.fr/rss", "https://cyber.gouv.fr/actualites/rss/")
test_feed("cyber.gouv.fr/atom", "https://cyber.gouv.fr/actualites/atom/")

print("\n=== HUDSON ROCK ===")
test_feed("Hudson Rock Substack", "https://hudsonrock.substack.com/feed")

print("\n=== BLEEPING COMPUTER Data Breach ===")
test_feed("BC ?cat=data-breach", "https://www.bleepingcomputer.com/feed/?cat=data-breach")

print("\n=== MANDIANT replacements ===")
test_feed("Sekoia Blog", "https://blog.sekoia.io/feed/")
test_feed("Cisco Talos", "https://blog.talosintelligence.com/rss/")
test_feed("ESET WeLiveSecurity", "https://www.welivesecurity.com/feed/")
test_feed("Palo Alto Unit42", "https://unit42.paloaltonetworks.com/feed/")

print("\n=== LEMAGIT replacements ===")
test_feed("Silicon.fr Sécurité", "https://www.silicon.fr/feed/")
test_feed("Global Security Mag", "https://www.globalsecuritymag.fr/rss.xml")
test_feed("InformatiqueNews", "https://www.informatiquenews.fr/feed")
