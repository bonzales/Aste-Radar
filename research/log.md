# log.md — log di sviluppo (append-only, greppabile)

Una riga per sessione produttiva. Formato:

```
YYYY-MM-DD | <area> | fatto: <cosa> | imparato: <cosa> | next: <cosa>
```

Aree tipiche: `bootstrap`, `scraper`, `downloader`, `parser`, `extractor`,
`scorer`, `notifier`, `wiki`, `docs`, `infra`. Non cancellare righe: si appende.

---

2026-07-05 | bootstrap | fatto: inizializzato lo scheletro del repo secondo CLAUDE.md §2 (config/ raw/ db/ src/ research/ docs/ tests/), .gitignore con secrets.env e raw/ e db/ esclusi, README quickstart, template config (comuni.yaml, scoring.yaml, secrets.env.example), wiki research/ seminata da CLAUDE.md §11 | imparato: repo era completamente vuoto (nessun commit); decisioni §12 (comuni+tribunali, pesi griglia, modello LLM, reddito-vs-flip) ancora aperte e bloccano scraper e scorer | next: brainstorming Fase 1 (MVP notifica grezza) — prima sciogliere l'elenco comuni + verificare tribunale competente sul PVP
