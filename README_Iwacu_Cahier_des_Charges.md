# MVP Chatbot « Iwacu » — Cahier des charges (README)

> **Version** : 2025-09-04 19:56  
> **Portée** : Cahier des charges **métier** (fonctionnel) + **technique** + **architecture** pour le MVP.

---

## Sommaire
- [1) Contexte & objectifs métier](#1-contexte--objectifs-métier)
- [2) Périmètre (In/Out)](#2-périmètre-inout)
- [3) Parcours & User Stories](#3-parcours--user-stories)
- [4) Règles métier](#4-règles-métier)
- [5) KPIs & critères d’acceptation](#5-kpis--critères-dacceptation)
- [6) Cahier des charges technique](#6-cahier-des-charges-technique)
  - [6.1 Stack & composants](#61-stack--composants)
  - [6.2 Endpoints API](#62-endpoints-api)
  - [6.3 Modèle de données](#63-modèle-de-données)
  - [6.4 Intégrations & auth](#64-intégrations--auth)
  - [6.5 Observabilité, qualité & tests](#65-observabilité-qualité--tests)
  - [6.6 Configuration (.env)](#66-configuration-env)
  - [6.7 Déploiement](#67-déploiement)
  - [6.8 Sécurité & conformité](#68-sécurité--conformité)
- [7) Architecture](#7-architecture)
- [8) Roadmap & risques](#8-roadmap--risques)
- [Annexes](#annexes)

---

## 1) Contexte & objectifs métier
- Réduire la charge sur l’équipe Iwacu face aux **demandes récurrentes** : *menu, promos, horaires (+ exceptions)*.
- **Prendre une réservation simple** en < 30 secondes.
- **Multicanal** : widget web + WhatsApp (Cloud API Meta).
- **Bilingue FR/EN** (auto-détection simple).
- **Suivi** via un **dashboard** minimal (conversations, taux de fallback).

## 2) Périmètre (In/Out)
**In scope (MVP)**
- Intents : `menu`, `promos`, `horaires`, `booking`, `fallback`.
- Widget web statique + intégration **WhatsApp Cloud API (sandbox)**.
- Réservation : date, heure, nb personnes, nom, téléphone, zone (int./ext.), notes.
- **Stockage** : Google Sheets (si auth) ou **CSV fallback**.
- **ICS** (90 minutes) et **(option)** Google Calendar.
- **Dashboard** Streamlit : nb conversations, messages, fallback rate.

**Out of scope (MVP)**
- Paiement, plan de salle, inventaire, emailing, analytics avancés, LLM complexe.

## 3) Parcours & User Stories
- **US-1** Voir le menu → renvoyer quelques items + prix (aperçu).
- **US-2** Horaires du jour → ouvert/fermé + tranches horaires (exceptions incluses).
- **US-3** Promos/Happy hour → promo active/à venir + plage horaire + notes.
- **US-4** Réserver → saisie date/heure/nb/nom/tél → **booking_id** + **.ics** ; stockage Sheet/CSV ; (option) Calendar.
- **US-5** Staff Iwacu → consulter le **dashboard** (KPI).

## 4) Règles métier
- **Horaires** : base hebdo (`hours.csv`) + **exceptions** (`hours_exceptions.csv`) **priment** sur la base.
- **Promos** : `active` si `now ∈ [start, end]`, `starting_soon` si commence ≤ 60 min.
- **Réservation** : slot **90 min**, refuser date/heure passées, données minimales (date, heure, nb, nom/tel).
- **Langue** : heuristiques (stopwords + accents) → gabarits FR/EN.
- **Fallback** : message d’aide si l’intent est inconnu.

## 5) KPIs & critères d’acceptation
**KPIs**
- Nb conversations, nb messages, **fallback rate**, nb réservations créées.

**Acceptation (MVP validé si)**
1) Les 4 intentions (menu/promos/horaires/booking) répondent correctement **en FR & EN**.  
2) `POST /booking` crée une ligne dans **Google Sheets** (ou CSV fallback) et génère un **.ics** téléchargeable.  
3) Le **widget web** répond correctement et initie une mini-réservation.  
4) Le **webhook WhatsApp** passe la vérification et renvoie une réponse utilisateur.  
5) Le **dashboard** affiche les KPIs basiques.

---

## 6) Cahier des charges technique

### 6.1 Stack & composants
- **Langage** : Python **3.11+**
- **API** : FastAPI + Uvicorn
- **NLP minimal** : règles regex + détection FR/EN (stopwords/accents)
- **Données** : CSV (`menu.csv`, `promos.csv`, `hours.csv`, `hours_exceptions.csv`) ; **Réservations** en **Google Sheets** via `gspread` *(ou CSV fallback)* ; **ICS** local ; **(option)** Google Calendar via `google-api-python-client`
- **Multicanal** : widget web statique + **WhatsApp Cloud API** (relay webhook)
- **Dashboard** : Streamlit (lecture `conversations.jsonl`)

### 6.2 Endpoints API
```
GET  /health                 → {"status":"ok","tz":"Europe/Paris"}
GET  /menu                   → {"items":[{id,name,price,category},...]}
GET  /promos[?at=ISO8601]    → {"active":[...],"starting_soon":[...],"today":[...]}
GET  /horaires               → {"week":[...], "exceptions":[...]}
GET  /horaires/today         → {"status":"open|closed|unknown","open_time","close_time"}
POST /chat {text,sender?}    → {"reply", "intent", "lang"}
POST /booking {...}          → {"ok","booking_id","storage":"csv|google_sheets","ics_url","calendar":null|"google_calendar:*"}
GET  /booking/ics/{id}       → (text/calendar) ICS
GET  /widget                 → HTML widget
```

### 6.3 Modèle de données
- **menu.csv** : `id,name,price,category`  
- **promos.csv** : `name,day,start_time,end_time,notes`  
- **hours.csv** : `day,open,close`  
- **hours_exceptions.csv** : `date,open,close,reason`  
- **bookings.csv** (fallback) / **Google Sheet** (onglet `reservations`) :  
  `booking_id,date,time,party_size,area,name,phone,notes,source,created_at`  
- **conversations.jsonl** : `{event:'user|bot', text, intent, sender, timestamp}`

### 6.4 Intégrations & auth
- **Google Sheets/Calendar** : privilégier **ADC** (Colab/GCP) ou **OAuth** (`gspread.oauth()`), sinon **Service Account** (secrets cloud).
- **WhatsApp Cloud API** : webhook **GET verify** (challenge), **POST events**, réponse via **Graph API** (token).

### 6.5 Observabilité, qualité & tests
- **Logs** : `conversations.jsonl` (événements user/bot, intent, timestamp).
- **Scripts** : `preflight_check.py` (vérifs env/ports/CSV/modules), `smoke_test_local.py` (tests endpoints).
- **Tests unitaires** : parsing horaires + exceptions ; classification promos (bords) ; détection intent ; génération ICS.
- **Performance** cible : < 300 ms endpoints simples local ; < 1 s pour booking (sans Calendar).

### 6.6 Configuration (.env)
```ini
TIMEZONE=Europe/Paris
MENU_CSV=./data/menu.csv
PROMOS_CSV=./data/promos.csv
HORAIRES_CSV=./data/hours.csv
EXCEPTIONS_CSV=./data/hours_exceptions.csv

GSPREAD_SHEET_NAME=IwacuBookings
GSPREAD_WORKSHEET=reservations

# Option (non sensible)
GOOGLE_CALENDAR_ID=xxxxxxxx@group.calendar.google.com

# WhatsApp sandbox (mettre comme secrets en cloud)
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
META_VERIFY_TOKEN=...
```
> **Éviter** de stocker des secrets en clair. En local, préférer ADC/OAuth. En cloud, utiliser les **secrets** de la plateforme (Railway/Fly/etc.).

### 6.7 Déploiement
- **Local**  
  ```bash
  # API
  uvicorn services.api.app:app --host 0.0.0.0 --port 8080 --reload
  # Dashboard
  streamlit run services.dashboard.streamlit_app.py
  # Relay WhatsApp
  uvicorn services.relay.whatsapp_relay:app --port 8081 --reload
  ```
- **Cloud** (Railway / Fly.io) : services séparés (API, relay, dashboard), domaine + HTTPS, secrets gérés par la plateforme.
- **CI/CD** : GitHub Actions (lint/tests + déploiement conditionnel).

### 6.8 Sécurité & conformité
- Scopes Google minimaux (Sheets/Drive/Calendar si activé).
- Tokens WhatsApp en **secrets** ; pas de PII inutile en logs.
- HTTPS, CORS restreint, validation Pydantic ; conformité **RGPD** (effacement sur demande).

---

## 7) Architecture

### 7.1 Vue d’ensemble (Mermaid)
```mermaid
flowchart LR
  subgraph Channels
    W(Web Widget)
    WA(WhatsApp Cloud API)
  end

  subgraph Relay
    R[Webhook Meta]
  end

  subgraph API[FastAPI]
    CHAT[/POST /chat/]
    MENU[/GET /menu/]
    PROMOS[/GET /promos/]
    HOURS[/GET /horaires, /horaires/today/]
    BOOK[/POST /booking/]
    ICS[/GET /booking/ics/{id}/]
  end

  subgraph Core
    NLP[(Regex FR/EN)]
    DATA[(CSV: menu, promos, hours, exceptions)]
    SHEETS[(Google Sheets)]
    ICSF[(ICS files)]
    GCAL[(Google Calendar optional)]
    LOGS[(conversations.jsonl)]
  end

  subgraph Dashboard
    D[Streamlit KPIs]
  end

  W --> CHAT
  WA --> R --> CHAT
  CHAT --> NLP --> DATA
  CHAT --> MENU
  CHAT --> PROMOS
  CHAT --> HOURS
  BOOK --> SHEETS & ICSF --> GCAL
  LOGS --> D
```

### 7.2 Séquences clés
- **Chat Web** : widget → `POST /chat` → NLP (intent+langue) → récupération données → **réponse**.
- **Booking** : `POST /booking` → validation → **Sheets/CSV** → **ICS** → (option) **Calendar** → **booking_id + ics_url**.
- **WhatsApp** : Meta → relay (verify GET/POST) → `/chat` → **réponse** via Graph API.

---

## 8) Roadmap & risques
**Roadmap**
- Intents avancés (allergènes, panier, paiement)
- NLP ML (scikit-learn / transformers)
- Analytics ROI, monitoring/observabilité

**Risques & parades**
- GSheets indispo → **CSV fallback**
- Tunnel WhatsApp down → **démo via widget local**
- Internet KO → **mode local + captures Calendar**
- Ports en conflit → **alternatifs** (8084/8085/8505)

---

## Annexes
- **PDF** plus formel : `docs/cahier-des-charges/Iwacu_Cahier_des_Charges_v2.pdf`
- Scripts utiles : `preflight_check.py`, `smoke_test_local.py`
- Données : `data/menu.csv`, `data/promos.csv`, `data/hours.csv`, `data/hours_exceptions.csv`
