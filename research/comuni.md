# comuni.md — note per microzona (distretto di Venezia)

Qui vive il **vantaggio informativo** dell'utente: conosce le microzone perché ci
abita. Codificare questa conoscenza qui evita di indovinare (o di lasciarla nella
testa dell'utente). Alimenta `config/comuni.yaml` (dove scansionare) e le
`zone_ammesse` di `config/scoring.yaml`.

## Come si struttura una nota comune

Per ogni comune/microzona, annotare quando emerge dall'esperienza:
- **Tribunale competente** — VERIFICATO sul PVP, non assunto (CLAUDE.md §8, §12).
- **Zona (A/B/C)** — classificazione interna usata dalla griglia; il criterio è
  dell'utente (centralità, servizi, domanda locativa/turistica, insidie).
- **Note operative** — quartieri da evitare, aree alluvionali, cantieri, ecc.

## Decisione PRESA (2026-07-05): filtro geografico, non per tribunale

Il criterio di inclusione è **l'ubicazione dell'immobile**, NON il tribunale che
gestisce la vendita. Un lotto di un tribunale qualsiasi (anche fuori regione)
rientra se l'immobile è nelle zone target. → La questione "quale tribunale copre
Spinea/Mirano/…" **non è più un gate**: si cerca per geografia sul PVP.

Zone target:
- **Tutta la provincia di Venezia (VE)**. L'utente è **cresciuto a Mestre**
  (frazione del Comune di Venezia): massimo vantaggio informativo nell'area
  mestrina e nella terraferma veneziana.
- **Comune di Treviso** (capoluogo).
- **Comuni della provincia di Treviso limitrofi a VE** — proposta iniziale in
  `config/comuni.yaml` (`comuni_extra`, `attivo: false` finché non confermati):
  Mogliano Veneto, Preganziol, Casale sul Sile, Casier, Silea, Zero Branco,
  Quinto di Treviso. Da rivedere con l'utente.

## Ancora da sciogliere

- [ ] Confermare/rifinire l'elenco dei comuni TV limitrofi (attivarli in config).
- [ ] Classificazione di zona (A/B/C) per la griglia — criterio dell'utente,
      non inventato. Mestre/terraferma vs Venezia insulare vs entroterra hanno
      dinamiche di flip molto diverse.

## Note per comune

_(Da compilare con l'utente. Priorità: microzone dell'area mestrina/terraferma
dove il vantaggio informativo è massimo. Non inventare classificazioni di zona.)_
