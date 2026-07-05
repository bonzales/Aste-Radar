# log.md — log di sviluppo (append-only, greppabile)

Una riga per sessione produttiva. Formato:

```
YYYY-MM-DD | <area> | fatto: <cosa> | imparato: <cosa> | next: <cosa>
```

Aree tipiche: `bootstrap`, `scraper`, `downloader`, `parser`, `extractor`,
`scorer`, `notifier`, `wiki`, `docs`, `infra`. Non cancellare righe: si appende.

---

2026-07-05 | bootstrap | fatto: inizializzato lo scheletro del repo secondo CLAUDE.md §2 (config/ raw/ db/ src/ research/ docs/ tests/), .gitignore con secrets.env e raw/ e db/ esclusi, README quickstart, template config (comuni.yaml, scoring.yaml, secrets.env.example), wiki research/ seminata da CLAUDE.md §11 | imparato: repo era completamente vuoto (nessun commit); decisioni §12 (comuni+tribunali, pesi griglia, modello LLM, reddito-vs-flip) ancora aperte e bloccano scraper e scorer | next: brainstorming Fase 1 (MVP notifica grezza) — prima sciogliere l'elenco comuni + verificare tribunale competente sul PVP
2026-07-05 | wiki | fatto: sciolte 3 decisioni §12 con l'utente e scritta la spec Fase 1 (research/fase1-mvp-spec.md) | imparato: (1) filtro GEOGRAFICO sull'ubicazione immobile, NON per tribunale → si cerca per provincia/comune sul PVP; zone = provincia VE intera + comune di Treviso + comuni TV limitrofi (da confermare); utente cresciuto a Mestre. (2) griglia specializzata sul FLIP <5 anni. (3) estrazione con Haiku 4.5 + escalation. Rischio n.1 Fase 1: non è verificato come risponde il PVP a httpx (possibile JS/anti-bot) → serve uno spike prima di scrivere lo scraper | next: attendere ok utente sulla spec + rispondere alle 4 domande aperte (bot Telegram dedicato o riuso Kraken, lista comuni TV, orario cron, tipologia immobili); poi spike PVP
2026-07-05 | wiki | fatto: confermati i 4 parametri Fase 1 con l'utente e recepiti in config | imparato: bot Telegram DEDICATO (riuso codice Kraken, canale separato); 7 comuni TV limitrofi tutti attivi in config/comuni.yaml; cron giornaliero 07:00; tipologia SOLO residenziale (aggiunto blocco `tipologie` in comuni.yaml). Spec Fase 1 ora senza domande aperte | next: spike PVP (verificare come risponde la ricerca immobili per provincia/comune: HTML statico vs JS/anti-bot, parametri query, id stabile del lotto) → poi scraper
