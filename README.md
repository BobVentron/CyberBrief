<div align="center">

# CyberBrief v2

**Veille cybersecurite automatisee — self-hosted, propulsee par Claude AI, panel admin complet.**

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Node.js](https://img.shields.io/badge/Node.js-20-green?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docs.docker.com/compose/)
[![Claude API](https://img.shields.io/badge/Claude-API-orange?logo=anthropic&logoColor=white)](https://console.anthropic.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Licence](https://img.shields.io/badge/Licence-MIT-green)](LICENSE)

> CyberBrief scrape 24 sources RSS + l'API NVD, genere un briefing HTML via Claude, l'envoie par email, et expose tout ca sur une interface web securisee avec authentification JWT et panel d'administration complet.

</div>

---

## Table des matieres

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture](#architecture)
3. [Structure du projet](#structure-du-projet)
4. [Sources](#sources)
5. [Contenu des rapports](#contenu-des-rapports)
6. [Prerequis](#prerequis)
7. [Installation](#installation)
8. [Configuration](#configuration)
9. [Panel admin](#panel-admin)
10. [Couts estimes](#couts-estimes)
11. [Depannage](#depannage)
12. [Disclaimer](#disclaimer)

---

## Vue d'ensemble

CyberBrief est un outil de veille cyber personnel et self-hosted. Il collecte et analyse automatiquement les evenements de securite depuis 24 sources de confiance, filtre les incidents touchant la France, correleles CVEs depuis le NVD, et utilise Claude pour produire un briefing structure de niveau analyste.

**Pas de SaaS. Pas d'abonnement. Pas de tracking. Tes donnees restent sur ton serveur.**

### Fonctionnalites

| Fonctionnalite | Description |
|----------------|-------------|
| Authentification JWT | Inscription, connexion, refresh token rotatif, verification email |
| Envoi mail automatique | Rapports envoyes par SMTP aux adresses configurees par chaque utilisateur |
| Dashboard utilisateur | Parametrage de 1 a 5 adresses de reception, toggles quotidien/hebdo |
| RGPD / NIS-2 | Consentement, export JSON, suppression, audit log, anonymisation |
| Panel administration | Stats, graphiques Chart.js, gestion users, logs email, couts API |
| Tracking couts Claude | Chaque rapport logge les tokens et le cout |
| Planification double | Planning distinct pour le brief quotidien et le recap hebdomadaire |
| Sante des sources | Statut OK/KO de chaque source RSS apres chaque execution |
| Logs en direct | Suivi des logs de la derniere execution depuis le panel admin |
| Destinataires admin | Ajouter/supprimer des emails depuis l'admin sans inscription |
| Rapports indexes | Liste des briefs generes avec apercu iframe et lien direct |
| PostgreSQL | Base de donnees via Prisma ORM, migrations automatiques |

---

## Architecture

```
[Daemon Python - APScheduler]
    |
    +-- brief-daily  (cron configurable, ex: 21h lun-ven)
    +-- brief-weekly (cron configurable, ex: 21h sam)
            |
            +-- scraper/scraper.py       <- 24 flux RSS + API NVD
            +-- briefing/generator.py    <- Claude API genere le rapport HTML
            +-- notifier/gotify.py       <- Sauvegarde + log couts + mail + Gotify
                        |
                        +-- POST /api/internal/api-usage
                        +-- POST /api/mailer/send-report
                        +-- Gotify push

[cyberbrief-api - Node.js/Express]
    +-- /api/auth/     <- Inscription, connexion, refresh, reset password
    +-- /api/users/    <- Profil, preferences mail, droits RGPD
    +-- /api/mailer/   <- Envoi rapport SMTP
    +-- /api/admin/    <- Stats, graphiques, rapports, sources, logs, destinataires
    +-- /api/internal/ <- Endpoints proteges token interne

[cyberbrief-web - Nginx public]
    +-- /              <- Index rapports
    +-- /login         <- Connexion
    +-- /register      <- Inscription
    +-- /dashboard     <- Tableau de bord utilisateur
    +-- /reports/      <- Rapports HTML

[cyberbrief-admin - Nginx admin]
    +-- /              <- Panel administration (protege Authelia)
```

**5 containers Docker :**

| Container | Role | Reseau |
|-----------|------|--------|
| `cyberbrief-db` | PostgreSQL 16 | interne |
| `cyberbrief-api` | Node.js API | interne |
| `cyberbrief-app` | Python daemon | interne |
| `cyberbrief-web` | Nginx public | proxy + interne |
| `cyberbrief-admin` | Nginx admin | proxy + interne |

---

## Structure du projet

```
cyberbrief/
|-- docker-compose.yml
|-- Dockerfile
|-- requirements.txt
|-- main.py                    <- Daemon APScheduler (2 jobs: daily + weekly)
|-- .env.example
|
|-- scraper/
|   |-- sources.py             <- 24 sources RSS
|   +-- scraper.py             <- Collecte RSS + NVD, sante sources
|
|-- briefing/
|   +-- generator.py           <- Prompts Claude
|
|-- notifier/
|   +-- gotify.py              <- Sauvegarde + manifest.json + mail + Gotify
|
|-- api/
|   |-- prisma/schema.prisma
|   +-- src/
|       |-- auth/routes.js
|       |-- users/routes.js
|       |-- mailer/routes.js   <- Envoi aux users + extra_recipients
|       |-- admin/routes.js    <- Stats, rapports, sources, logs, destinataires
|       +-- internal/routes.js <- api-usage, settings
|
+-- nginx/
    +-- pages/
        |-- login.html
        |-- register.html
        |-- dashboard.html
        +-- admin.html         <- Panel admin (SPA)
```

---

## Sources

### Francophones (8)

| Source | Type |
|--------|------|
| CERT-FR Alertes | Alertes officielles |
| CERT-FR Avis | Avis officiels |
| ANSSI / cyber.gouv.fr | Agence nationale de securite |
| IT-Connect | Actu securite FR |
| Zataz | Fuites & incidents FR |
| LeMagIT Securite | Securite entreprise FR |
| 01net Securite | Actu IT securite FR |
| Silicon.fr | Tech & entreprise FR |

### Trackers fuites & breaches (7)

| Source | Specialite |
|--------|-----------|
| Ransomware.live | Tracker victimes ransomware |
| DataBreaches.net | Base fuites de donnees |
| BleepingComputer Data Breach | Reporting fuites |
| Hudson Rock | Infostealers & credentials |
| Privacy Affairs | Dark web |
| Flashpoint Blog | Threat intel dark web |
| Recorded Future | APT & threat intelligence |

### Actualites internationales (9)

| Source | Specialite |
|--------|-----------|
| The Hacker News | Actu cybersecurite |
| BleepingComputer | Incidents, ransomware |
| Krebs on Security | Investigations |
| Dark Reading | Threat intel entreprise |
| Schneier on Security | Analyse & politique |
| SANS Internet Stormcast | Analyse technique |
| Cisco Talos Intelligence | Threat intel, APT, malware |
| Palo Alto Unit 42 | Threat intel, APT |
| Mandiant Blog | Recherche APT |

### CVE

API NVD (NIST) — CVEs avec CVSS >= 7.0 des dernieres 24h (ou 7 jours en mode hebdo).

---

## Contenu des rapports

### Brief quotidien

| Section | Contenu |
|---------|---------|
| Incidents & Attaques | Campagnes actives, nouvelles techniques |
| France - Piratages & Fuites | Entites francaises : nom, secteur, donnees, acteur, source |
| Monde - Piratages & Fuites | Breaches internationaux |
| CVEs critiques | Focus exploitation in-the-wild |
| Outils & Publications | Nouveaux outils, recherche |
| A surveiller | 2-3 points de vigilance pour les 24-48h suivantes |

### Recap hebdomadaire

Version etendue : fil rouge narratif, top 5 breaches monde, tendances CVE, stats de la semaine, watchlist etendue.

---

## Prerequis

- Un VPS ou serveur Linux (Ubuntu 22.04+)
- Docker + Docker Compose v2
- Une cle API Anthropic
- Un compte SMTP (Gmail, OVH, Brevo, Mailgun...)
- *(Optionnel)* Authelia pour proteger le panel admin

---

## Installation

### 1. Cloner le depot

```bash
git clone https://github.com/BobVentron/CyberBrief.git
cd CyberBrief
```

### 2. Configurer l'environnement

```bash
cp .env.example .env
nano .env
```

Variables obligatoires :

```env
DB_PASSWORD=mot_de_passe_fort
JWT_SECRET=...              # node -e "console.log(require('crypto').randomBytes(64).toString('hex'))"
JWT_REFRESH_SECRET=...
INTERNAL_API_TOKEN=...      # openssl rand -hex 24
ADMIN_API_TOKEN=...
ANTHROPIC_API_KEY=sk-ant-...
SMTP_HOST=ssl0.ovh.net
SMTP_PORT=587
SMTP_USER=votre@email.com
SMTP_PASSWORD=...
REPORT_BASE_URL=https://cyberbrief.votre-domaine.com
```

### 3. Creer le reseau Docker externe

```bash
docker network create proxy
```

### 4. Demarrer

```bash
docker compose up -d --build
docker compose ps
```

Les migrations PostgreSQL sont appliquees automatiquement.

### 5. Creer le premier compte

Ouvrir `https://cyberbrief.votre-domaine.com/register` et verifier l'email recu.

---

## Configuration

### Planification

Configurable depuis le panel admin, section **Planification** — aucun redemarrage requis.

Defauts :
- Brief quotidien : `0 21 * * 1-5` (lun-ven 21h)
- Recap hebdomadaire : `0 21 * * 6` (samedi 21h)

Le daemon lit les plannings depuis la base de donnees toutes les 30 secondes.

### Modele Claude

Configurable depuis le panel admin. Modeles disponibles :

| Modele | Cout indicatif | Usage |
|--------|---------------|-------|
| `claude-sonnet-4-6` | ~$0.05/rapport | Recommande |
| `claude-opus-4-8` | ~$0.20/rapport | Qualite maximale |
| `claude-haiku-4-5-20251001` | ~$0.01/rapport | Economique |

---

## Panel admin

Accessible sur le sous-domaine admin, protege par Authelia (aucun formulaire de connexion dans le code).

### Sections

| Section | Contenu |
|---------|---------|
| Vue d'ensemble | KPIs (users, emails, cout API, rapports) + graphiques 30j |
| Couts API | Cout total, par rapport, graphiques tokens/cout |
| Planification | Planning quotidien + hebdo independants, choix modele Claude |
| Logs en direct | Logs de la derniere execution, suivi polling 2s |
| Rapports | Liste des briefs generes avec apercu iframe |
| Sante sources | Statut OK/KO des 24 sources RSS |
| Destinataires | Ajouter/supprimer des emails hors inscription |
| Utilisateurs | Liste paginee, activer/desactiver/supprimer |
| Logs email | Historique envois avec statut sent/failed |
| Journal d'audit | Actions sensibles (login, register, changement mdp...) |

### Configuration NPM

1. Proxy host `admin.cyberbrief.domaine.com` -> `cyberbrief-admin:80`
2. Activer Forward Auth vers Authelia
3. Restreindre l'acces a l'IP LAN ou VPN

---

## Couts estimes

| Poste | Cout |
|-------|------|
| claude-sonnet-4-6 — quotidien (~15K tokens) | ~$0.05/jour ~ $1.50/mois |
| claude-sonnet-4-6 — hebdo (~40K tokens) | ~$0.15/semaine ~ $0.60/mois |
| VPS 2Go RAM | $3-5/mois |
| **Total estime** | **~$5-7/mois** |

Les couts reels sont traces dans le panel admin (graphique jour par jour).

---

## Depannage

**Les containers ne demarrent pas**
```bash
docker compose logs
docker network ls    # verifier que "proxy" existe
```

**L'API ne repond pas**
```bash
docker logs cyberbrief-api --tail 50
```
Verifier que `JWT_SECRET` et `DB_PASSWORD` sont dans `.env`.

**Les emails ne partent pas**
```bash
docker logs cyberbrief-api | grep MAILER
```
Pour Gmail : utiliser un App Password, pas le mot de passe du compte.

**"Sante sources" affiche "Erreur de chargement"**

Le container API n'est pas a jour : `docker compose up -d --build cyberbrief-api`

**"Sante sources" affiche "Aucune donnee"**

Aucun rapport n'a encore ete genere. Utiliser "Declencher maintenant" dans Planification.

**Reconstruire apres modification**
```bash
docker compose up -d --build
```

---

## Disclaimer

CyberBrief est un outil de veille personnelle a but informatif. Les rapports sont generes a partir de flux RSS publics et de l'API NVD.

Le contenu genere par l'IA peut contenir des inexactitudes. Verifier tout element critique aupres des sources originales.

Ce projet n'est affilie ni a Anthropic, ni a l'ANSSI, ni au CERT-FR.

---

<div align="center">

Python + Node.js · Propulse par l'[API Claude](https://console.anthropic.com/) · Self-hosted

</div>
