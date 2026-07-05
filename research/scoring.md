# scoring.md — razionale della griglia

Qui vive il **perché** dietro `config/scoring.yaml`. Il file YAML dice i numeri;
questa pagina dice il ragionamento. Regola: nessun valore entra in produzione
(`tarato: true`) senza una riga di giustificazione qui.

## Filosofia (CLAUDE.md §5 — gate "segnala o scarta")

La griglia serve a non annegare nei falsi positivi né a perdere l'affare vero.
Due livelli:

1. **Criteri HARD** — gate binari. Se un lotto ne fallisce anche uno solo →
   scarto silenzioso, niente notifica. Non si ammorbidiscono per "far passare
   più roba": in asta la disciplina è tutto. Se in una settimana non passa nulla
   è il comportamento corretto (ma verifica che lo scraper giri — fail loud, §1.4).
2. **Pesi SOFT** — servono solo a ordinare/priorizzare i lotti che hanno già
   passato tutti i gate hard. Producono il punteggio e la motivazione leggibile.

## Criteri hard — perché ciascuno

- **Sconto minimo sulla stima** — la ragione d'essere: comprare sotto valore.
  Soglia da decidere (§12). Nota: il prezzo base d'asta è già scontato per legge
  di ribasso in ribasso; la stima peritale è il riferimento di valore.
- **Zona ammessa** — vedi `comuni.md`. L'utente conosce le microzone (vive lì):
  vantaggio informativo da codificare, non da indovinare.
- **Categoria catastale** — legata al prezzo-valore (`fiscale.md`): uso abitativo
  (cat. A tranne A/10) da persona fisica → imposte sul valore catastale, non sul
  prezzo. Vantaggio fiscale che orienta le categorie ammesse.
- **Occupazione** — libero = ottimo; occupato dal debitore = liberabile via
  custode/giudice; contratto opponibile (data certa anteriore al pignoramento) =
  scarto per uso proprio/turistico (`fiscale.md`).
- **Abusi/difformità insanabili** — possono affondare l'operazione: scarto hard.

## Obiettivo PRESO (2026-07-05): FLIP (rivendita <5 anni)

La griglia si specializza sul **flip**, non sul reddito da locazione. Conseguenze
sui criteri e sui pesi:

- **Sconto sulla stima** = criterio dominante. È il margine lordo di partenza.
- **Ristrutturabilità** conta: un immobile da rimettere a posto con costo
  prevedibile e rivendibile in fretta batte uno "pronto" ma senza margine.
- **Liberabilità rapida** pesa: il flip vuole possesso e cantiere presto; un
  occupato che si libera in tempi lunghi erode il margine (costi di possesso).
- **Fiscalità <5 anni**: la plusvalenza da rivendita entro 5 anni è tassata
  (sostitutiva 26% o IRPEF, vedi `fiscale.md`). Il punteggio segnala il margine
  LORDO; l'utile netto va sempre calcolato a parte (Fase 4, checklist costi).
- Il rendimento locativo NON entra nella griglia (obiettivo diverso). Se in
  futuro si volesse un secondo profilo "reddito", si annota qui come scelta nuova.

## Pesi soft — perché

DA DECIDERE i numeri con l'utente (§12), ma con la bussola "flip" sopra. Vedi
`fiscale.md` per la differenza fra margine teorico d'asta e utile netto.

## Decisioni aperte tracciate qui

- [x] Reddito vs flip → **FLIP** (2026-07-05). Griglia specializzata.
- [ ] Sconto minimo su stima (numero) — criterio dominante per il flip.
- [ ] Zone ammesse (A/B/C) — dipende da `comuni.md`.
- [ ] Categorie catastali ammesse.
- [ ] Superficie min/max.
- [ ] Pesi soft e soglia di notifica.
- [ ] Come pesare ristrutturabilità e liberabilità (dati non sempre in perizia).
