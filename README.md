# Alba — mini-agente di briefing del mattino

**Entry per Hacksgiving 2026 di Fly.io** (23–29 nov 2026, consegna entro
mezzanotte PST di domenica 29 nov).

Alba è un agente personale che ogni mattina alle **07:17 (Europe/Rome)**
compone e consegna su Telegram un briefing in italiano: meteo, appuntamenti
del giorno, attività notturna dei repo GitHub. Gira su uno **Sprite Fly.io**
(microVM Linux isolata e persistente) e usa i **connettori Sprites**.

Loop agente (semplice, senza framework): raccoglie le fonti → l'LLM decide
cosa è importante e scrive il briefing → consegna su Telegram.

## Come funziona

```
07:17 ──▶ meteo (Open-Meteo, HTTP diretta, niente auth)
      ──▶ calendario (link ICS privato Google, fetch + parsing)
      ──▶ GitHub (connettore Sprites: commit da ieri)
      ──▶ LLM (connettore Sprites OpenRouter managed: scrive il briefing)
      ──▶ Telegram (connettore Sprites Custom API: sendMessage)
```

Le credenziali vivono nell'organizzazione Sprites: lo Sprite chiama il
gateway (`https://api.sprites.dev/v1/gateway/<provider>/<connection>/<path>`)
e il gateway allega la credenziale. **Lo Sprite non vede mai nessun token.**
Il codice rifiuta persino di inviare un header `Authorization` al gateway.

Se una fonte fallisce, il briefing lo dice in una riga invece di morire.
Se l'LLM fallisce, c'è un fallback deterministico (template) così il
briefing arriva comunque.

## Setup in 5 passi

1. **Crea lo Sprite:**
   ```sh
   sprite create alba-dev
   ```
2. **Connettori** (dashboard Sprites → Connectors, policy con name prefix
   `alba`):
   - **GitHub** (OAuth) — attività dei repo
   - **OpenRouter** (managed) — l'LLM, senza account OpenRouter
   - **Telegram** (Custom API) — base URL `https://api.telegram.org`,
     token del bot: il token resta nel connettore, mai nel codice
3. **Configura:**
   ```sh
   git clone https://github.com/giulianogramaglia69-boop/Alba
   cd Alba
   python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
   cp config/alba.toml.example config/alba.toml
   # compila ics_url (link segreto iCalendar di Google Calendar),
   # telegram_chat_id e repos
   ```
4. **Servizio sullo Sprite + avvio:**
   ```sh
   sprite-env services create
   alba doctor   # deve dire "Tutto ok"
   alba serve    # loop giornaliero + HTTP :8080 (/healthz, /briefing)
   ```
5. **Prova:**
   ```sh
   alba briefing --dry-run   # dati fittizi, niente rete, niente invio
   alba briefing             # briefing vero, stampato (non inviato)
   alba briefing --send      # briefing vero + invio su Telegram
   ```

## Comandi

| Comando | Cosa fa |
|---|---|
| `alba doctor` | Controlla config, gateway, connettori, e che non ci siano token in env |
| `alba briefing [--dry-run] [--send]` | Genera e stampa il briefing (dry-run: dati fittizi) |
| `alba serve` | Loop alle 07:17 + server HTTP :8080 (`/healthz`, `/briefing`) |

## Struttura

```
src/alba/
  config.py        caricamento/validazione config TOML
  gateway.py       client gateway Sprites (rifiuta Authorization)
  weather.py       Open-Meteo (HTTP diretta, niente auth)
  calendar_ics.py  fetch + parsing ICS fatto a mano (stdlib)
  github_activity.py  commit recenti via connettore GitHub
  llm.py           chat completion via connettore OpenRouter
  telegram.py      sendMessage via connettore Custom API
  briefing.py      raccolta fonti + composizione (LLM o template)
  serve.py         scheduler 07:17 + server HTTP
  doctor.py        controlli pre-avvio
  cli.py           comandi doctor/briefing/serve
  fixtures.py      dati fittizi per dry-run e test
config/alba.toml.example   (il vero config resta fuori dal repo)
tests/           pytest offline (mock HTTP, niente rete nei test)
```

## Demo (dry-run)

```sh
$ alba briefing --dry-run
☀️ Buongiorno — mercoledì 25 novembre 2026

Data: mercoledì 25 novembre 2026 — Luogo: Agrigento
Meteo: Agrigento: parzialmente nuvoloso, min 15° / max 19°, probabilità di pioggia 10%, raffiche fino a 43 km/h
Appuntamenti di oggi:
  - 08:00–09:00 Lezione di matematica
  - 17:00–18:30 Palestra — gambe
Attività GitHub (da ieri):
  - giulianogramaglia69-boop/GG: 2 commit — Giuliano: feat(pkg): package manager v1 (+1 altri)
```

## Limiti onesti (v1)

- **Niente Gmail.** Google OAuth NON è un connettore Sprites e un access
  token Google scade dopo ~1h; un Custom API con token statico non può fare
  refresh. La v1 non include le email importanti (il briefing di Thalia le
  ha, Alba no). Estensione futura possibile: un ponte via Google Apps Script
  che spinge i dati allo Sprite — fuori scope v1.
- **Calendario via ICS privato**: dipende dal link segreto di Google Calendar
  (Google Calendar → Impostazioni → link segreto in formato iCalendar).
  Se il link viene revocato, `alba doctor` non lo vede: il briefing segnala
  "calendario non disponibile" e va rigenerato il link.
- **LLM**: dipende dal connettore OpenRouter managed e dal suo costo nel
  piano Sprites. I modelli free del catalogo ruotano: se il modello di
  default risponde "model not found", cambialo in `config/alba.toml`.
- **Gateway solo dallo Sprite**: le chiamate al gateway devono partire da
  dentro uno Sprite (firma Fly.io). Dal laptop o da altre macchine tornano
  403 — `alba doctor` lo dice in chiaro. I test usano un finto trasporto.

## Licenza

GPLv3 — tutto il codice deve essere libero. Vedi `LICENSE`.
