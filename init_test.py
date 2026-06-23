"""
init_test.py — Script à exécuter UNE FOIS dans le container cyberbrief-app
après le démarrage de la stack pour :
1. Créer un utilisateur de test dans la DB
2. Configurer l'envoi email vers bastien222004@outlook.fr
3. Déclencher immédiatement la génération d'un rapport

Usage :
    docker exec -it cyberbrief-app python init_test.py
"""

import os, sys, time, json, hashlib, uuid, requests
from dotenv import load_dotenv

load_dotenv()

API_URL       = os.environ.get("CYBERBRIEF_API_URL", "http://cyberbrief-api:8000")
API_TOKEN     = os.environ.get("INTERNAL_API_TOKEN", "")
TEST_EMAIL    = "bastien222004@outlook.fr"
TEST_PASS     = "TestCyberBrief2024!"
RECIPIENT     = "bastien222004@outlook.fr"

headers_internal = {"X-Internal-Token": API_TOKEN, "Content-Type": "application/json"}

def wait_api():
    print("⏳ Attente de l'API...")
    for i in range(20):
        try:
            r = requests.get(f"{API_URL}/api/health", timeout=3)
            if r.ok:
                print("✅ API disponible")
                return True
        except Exception:
            pass
        time.sleep(3)
        sys.stdout.write(".")
        sys.stdout.flush()
    print("\n❌ API indisponible")
    return False

def register_user():
    print(f"\n📧 Inscription de {TEST_EMAIL}...")
    r = requests.post(f"{API_URL}/api/auth/register", json={
        "email":        TEST_EMAIL,
        "password":     TEST_PASS,
        "consent_rgpd": True,
    }, timeout=10)

    if r.status_code == 201:
        print("✅ Compte créé")
        return True
    elif r.status_code == 409:
        print("ℹ️  Compte déjà existant")
        return True
    else:
        print(f"⚠️  Réponse: {r.status_code} — {r.text[:200]}")
        return False

def activate_user_direct():
    """Active le compte directement via la DB (bypass email verify)."""
    print("🔧 Activation du compte via DB...")
    import subprocess
    result = subprocess.run([
        "python", "-c", f"""
import os
os.environ.setdefault('DATABASE_URL', os.environ.get('DATABASE_URL',''))

# Utiliser psycopg2 si disponible, sinon requests vers l'API
try:
    import psycopg2
    db_url = os.environ.get('DATABASE_URL', '')
    # Extraire les params
    import urllib.parse
    u = urllib.parse.urlparse(db_url)
    conn = psycopg2.connect(
        host=u.hostname, port=u.port or 5432,
        dbname=u.path.lstrip('/'), user=u.username, password=u.password
    )
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_active=true WHERE email=%s", ('{TEST_EMAIL}',))
    conn.commit()
    cur.close()
    conn.close()
    print('DB OK')
except Exception as e:
    print('DB error:', e)
"""
    ], capture_output=True, text=True, env={**os.environ})
    print(result.stdout or result.stderr or "OK")

def login_user():
    print(f"\n🔑 Connexion...")
    r = requests.post(f"{API_URL}/api/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASS,
    }, timeout=10)
    if r.ok:
        token = r.json().get("access_token")
        print("✅ Connecté")
        return token
    print(f"❌ Login échoué: {r.status_code} — {r.text[:100]}")
    return None

def set_mail_prefs(token):
    print(f"\n📮 Configuration des préférences email → {RECIPIENT}...")
    r = requests.put(f"{API_URL}/api/users/me/preferences", json={
        "recipient_emails": [RECIPIENT],
        "send_daily":  True,
        "send_weekly": True,
    }, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=10)
    if r.ok:
        print("✅ Préférences enregistrées")
        return True
    print(f"❌ Erreur prefs: {r.status_code} — {r.text[:100]}")
    return False

def trigger_report():
    print("\n⚡ Déclenchement du rapport...")
    r = requests.put(
        f"{API_URL}/api/internal/settings/trigger_now",
        json={"value": "true"},
        headers=headers_internal,
        timeout=10,
    )
    if r.ok:
        print("✅ Trigger activé — le rapport va démarrer dans ~30 secondes")
        print("   Surveille les logs : docker logs cyberbrief-app -f")
    else:
        print(f"❌ Erreur trigger: {r.status_code} — {r.text}")

def main():
    print("=" * 55)
    print("  CyberBrief — Initialisation & Test")
    print("=" * 55)

    if not wait_api():
        sys.exit(1)

    register_user()

    # Activer le compte via un appel direct à l'API de vérification
    # (contournement : on cherche le token de vérification)
    print("\n🔧 Activation du compte (contournement email verify)...")
    # Essayer via psql direct
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            # Reconstruire depuis DB_USER / DB_PASSWORD
            user = os.environ.get("DB_USER", "cyberbrief")
            pwd  = os.environ.get("DB_PASSWORD", "")
            db_url = f"postgresql://{user}:{pwd}@cyberbrief-db:5432/cyberbrief"

        import psycopg2
        import urllib.parse
        u = urllib.parse.urlparse(db_url)
        conn = psycopg2.connect(
            host=u.hostname, port=u.port or 5432,
            dbname=u.path.lstrip('/'),
            user=u.username, password=u.password,
        )
        cur = conn.cursor()
        cur.execute("UPDATE users SET is_active = true WHERE email = %s RETURNING id", (TEST_EMAIL,))
        rows = cur.fetchall()
        conn.commit()
        cur.close()
        conn.close()
        if rows:
            print(f"✅ Compte activé (id: {rows[0][0][:8]}…)")
        else:
            print("⚠️  Utilisateur non trouvé en DB")
    except ImportError:
        print("⚠️  psycopg2 non disponible — activation manuelle requise")
    except Exception as e:
        print(f"⚠️  Erreur DB: {e}")

    token = login_user()
    if not token:
        print("\n💡 Si le login échoue, le compte n'est peut-être pas encore actif.")
        print("   Lance : docker exec -it cyberbrief-db psql -U cyberbrief -c")
        print(f"   \"UPDATE users SET is_active=true WHERE email='{TEST_EMAIL}';\"")
        sys.exit(1)

    set_mail_prefs(token)
    trigger_report()

    print("\n" + "=" * 55)
    print("✅ Init terminée — rapport en cours de génération")
    print(f"   📬 Email vers : {RECIPIENT}")
    print("   📋 Logs : docker logs cyberbrief-app -f")
    print("=" * 55 + "\n")

if __name__ == "__main__":
    main()
