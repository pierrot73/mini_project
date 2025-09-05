# Architecture — Iwacu MVP

> Vue d’ensemble des composants, flux, données et déploiement.

## 1) Diagramme global
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

## 2) Séquences clés
### 2.1 Chat Web
```mermaid
sequenceDiagram
  participant U as Utilisateur (Web)
  participant W as Widget
  participant A as API /chat
  participant C as Core NLP
  U->>W: Message (ex: menu ?)
  W->>A: POST /chat {text}
  A->>C: Détecter langue + intent
  C-->>A: intent=menu, lang=fr
  A-->>W: Réponse (items + prix)
  W-->>U: Affichage
```

### 2.2 Réservation
```mermaid
sequenceDiagram
  participant U as Client
  participant A as API /booking
  participant S as Google Sheets/CSV
  participant I as ICS
  participant G as Google Calendar (opt)
  U->>A: POST /booking {{ date, time, party_size, name, phone }}
  A->>S: Écrit ligne de réservation (ou CSV)
  A->>I: Génère fichier .ics (90min)
  A->>G: (Option) Crée event dans Calendar
  A-->>U: {{ ok, booking_id, ics_url }}
```

### 2.3 WhatsApp Cloud API (sandbox)
```mermaid
sequenceDiagram
  participant WA as WhatsApp (Meta)
  participant R as Relay Webhook
  participant A as API /chat
  WA->>R: GET verify (challenge)
  R-->>WA: 200 + challenge
  WA->>R: POST message event
  R->>A: POST /chat {text}
  A-->>R: Réponse texte
  R-->>WA: Message sortant (Graph API)
```

## 3) Données & schéma
- **CSV** : `menu.csv`, `promos.csv`, `hours.csv`, `hours_exceptions.csv`
- **Réservations** : Google Sheets (onglet `reservations`) ou `bookings.csv`
- **Logs** : `conversations.jsonl`
- **ICS** : 1 fichier par réservation (`/booking/ics/{id}`)

## 4) Déploiement
- **Local** : uvicorn (API), streamlit (dashboard), uvicorn (relay) + tunnel ngrok pour Meta
- **Cloud** : Railway/Fly.io, secrets protégés, domaine + HTTPS, services séparés

## 5) Sécurité
- ADC/OAuth pour Google (éviter secrets en clair)
- Tokens WhatsApp en secrets plateforme
- Validation Pydantic, CORS restreint, HTTPS en prod
