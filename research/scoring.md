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

## Il funnel a livelli (deciso 2026-07-05) — ottimizza costo e velocità

L'IA (a pagamento, ~1-3 cent/perizia con Haiku 4.5) tocca SOLO i lotti che passano
i filtri gratuiti precedenti:

- **Livello 0** (gratis): geografia — province VE/TV target.
- **Livello 1** (gratis, dati già nella ricerca PVP): categoria residenziale,
  occupazione (il PVP dà `disponibilita` gratis!), prezzo base ≤ tetto. Scarta la
  maggior parte a costo zero.
- **Livello 2** (~1-3 cent): scarica perizia → OCR → IA estrae valore stima,
  superficie, categoria catastale, occupazione classificata, piena proprietà,
  abusi. Applica i gate hard (sconto, proprietà, categoria fine, abusi).
- **Livello 3** (rimandato): margine di flip netto. Richiede assunzioni utente
  (rivendita €/mq, ristrutturazione €/mq per zona) → `calcola_margine_flip: false`.

## Soglie hard DECISE (2026-07-05) — in `config/scoring.yaml`

- **Sconto minimo su stima: 25%** (`sconto_min_su_stima: 0.25`). Il driver del flip.
- **Occupazione: libero + occupato dal debitore** (liberabile). Escluso il
  contratto opponibile (es. locazione turistica — vedi caso Giudecca).
- **Tetto prezzo base: 150.000 €** (liquidità pronta dell'utente; filtro Livello 1).
- **Solo piena proprietà**: esclusi quota/nuda proprietà/usufrutto/superficie.
- **Categorie**: appartamenti e case singole (A/1,2,3,4,5,7,8,11); esclusi A/10
  uffici, C/* box, D/* alberghi, terreni. (uso abitativo → vantaggio prezzo-valore.)
- **Abusi insanabili**: scarto hard.

Nota disciplina (§5): un dato mancante che impedisce di verificare un gate →
il lotto NON si notifica (resta in DB, recuperabile), non lo si "assume buono".

## Ancora aperte

- [ ] **Superficie min/max** (utente non ancora deciso).
- [ ] **Zone ammesse (A/B/C)** — dipende da `comuni.md` (mappa microzone dell'utente).
- [ ] Pesi soft oltre lo sconto (entrano con le zone e col margine di flip).
- [ ] Livello 3 (margine flip): rivendita €/mq e ristrutturazione €/mq per zona.
