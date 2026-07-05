# CLAUDE.md — Schema operativo del progetto `aste-radar`

> Questo file è la **schema** nel senso di Karpathy (LLM-Wiki): dice all'agente
> com'è strutturato il repository, quali convenzioni seguire e quali workflow
> rispettare. Non è documentazione per l'umano — quella sta in `docs/`,
> organizzata secondo Diátaxis. Questo file rende l'agente un **manutentore
> disciplinato** della pipeline e della conoscenza di dominio, non un chatbot.
>
> Leggi questo file all'inizio di OGNI sessione, prima di scrivere codice.
> Aggiornalo quando cambiano le convenzioni: tu e l'utente lo fate co-evolvere.

---

## 0. Cos'è questo progetto

`aste-radar` è un sistema automatico che ogni giorno:
1. scansiona le nuove aste immobiliari giudiziarie nei comuni target;
2. scarica gli allegati (perizia, avviso di vendita, ordinanza);
3. estrae i dati chiave dalle perizie (anche via OCR + LLM);
4. assegna un punteggio secondo una griglia di screening definita in `research/scoring.md`;
5. notifica su Telegram solo i lotti che superano la soglia.

Obiettivo dell'utente: individuare lotti sotto valore nel distretto di Venezia
(residenza propria) per investimento a reddito o flip, senza monitorare
manualmente i portali. Lo strumento è **personale**, non un servizio pubblico.

Non è: un servizio rivendibile, un aggregatore pubblico, un redistributore di
dati. Resta su questo piano per non violare i termini dei portali.

---

## 1. Principi guida (non negoziabili)

1. **La fonte grezza è immutabile.** I PDF scaricati e l'HTML originale finiscono
   in `raw/` e non si toccano mai più. Sono la fonte di verità. Ogni dato
   estratto deve poter essere ritracciato al file grezzo che l'ha generato.

2. **Estrazione tracciabile, mai inventata.** Se un dato non è nella perizia,
   il campo resta `null` — MAI stimato o riempito per plausibilità. Un valore
   inventato in una perizia può costare decine di migliaia di euro in asta.
   Meglio un `null` esplicito che un numero falso.

3. **Sviluppo incrementale, a fasi.** Non costruire tutto insieme. Ogni fase
   deve funzionare e dare valore da sola prima di passare alla successiva
   (vedi §4). Un MVP che gira oggi batte un sistema completo che gira "domani".

4. **Fail loud.** Se una scansione fallisce, il sistema DEVE segnalarlo su
   Telegram ("scansione fallita: <motivo>"). Il silenzio non deve mai essere
   ambiguo tra "nessun lotto nuovo" e "lo scraper è rotto".

5. **Rispetto delle fonti.** Rate limit onesti, user-agent identificabile,
   nessun sovraccarico dei portali della giustizia. Lo scraping di dati pubblici
   per uso personale è lecito; l'abuso no.

6. **La decisione finale è sempre umana.** Il tool segnala e assiste. Non fa
   offerte, non prende impegni, non calcola l'offerta "definitiva" come se fosse
   oro. Ogni lotto promettente va aperto, letto e visitato di persona.

---

## 2. Struttura del repository

```
CLAUDE.md            ← questa schema; l'agente la legge per prima
README.md            ← quickstart per l'umano
config/
  comuni.yaml        ← comuni target + tribunale di competenza
  scoring.yaml       ← soglie e pesi della griglia (il "cervello")
  secrets.env        ← token Telegram, API key (NON committare; in .gitignore)
raw/                 ← IMMUTABILE: PDF perizie, HTML lotti, per data/lotto
db/
  aste.sqlite        ← stato: lotti visti, punteggi, storico notifiche
src/
  scraper.py         ← fetch lotti nuovi dai portali
  downloader.py      ← scarica allegati in raw/
  parser.py          ← estrazione testo/OCR dalla perizia
  extractor.py       ← LLM: perizia → JSON strutturato
  scorer.py          ← applica la griglia, produce il punteggio
  notifier.py        ← invia su Telegram
  main.py            ← orchestratore, lanciato da cron
research/            ← wiki LLM (Karpathy): conoscenza di dominio persistente
  index.md           ← mappa della wiki
  log.md             ← log greppabile append-only delle sessioni
  scoring.md         ← razionale della griglia (perché quei pesi)
  comuni.md          ← note per microzona (dove ci vive l'utente: vantaggio info)
  perizie.md         ← pattern ricorrenti nelle perizie, insidie di parsing
  fiscale.md         ← note fisco: prezzo-valore, plusvalenza <5 anni, flip, P.IVA
docs/                ← Diátaxis (per l'umano)
  tutorials/         ← "il tuo primo giro di scansione"
  how-to/            ← "come aggiungere un comune", "come cambiare una soglia"
  reference/         ← comandi, schema DB, formato JSON estratto
  explanation/       ← perché questa architettura, lezioni dai progetti precedenti
tests/               ← test su perizie campione salvate
```

---

## 3. Il ciclo operativo: ingest → extract → score → notify

Ogni run giornaliero (cron) esegue in ordine:

1. **ingest** — `scraper.py` interroga i portali per i comuni in `config/comuni.yaml`,
   confronta con `db/aste.sqlite`, isola SOLO i lotti nuovi. `downloader.py`
   salva gli allegati in `raw/<data>/<id_lotto>/`.

2. **extract** — `parser.py` estrae il testo (OCR con pdftoppm + Tesseract se
   scansione). `extractor.py` passa il testo all'LLM con prompt strutturato e
   ottiene JSON: `{valore_stima, prezzo_base, superficie_mq, indirizzo, zona,
   occupazione, categoria_catastale, difformita, arretrati_condominiali, note}`.
   Campi non trovati → `null`.

3. **score** — `scorer.py` applica `config/scoring.yaml`. Produce punteggio +
   motivazione leggibile ("prezzo 30% sotto stima, libero, zona B, cat. A/2").

4. **notify** — `notifier.py` invia su Telegram i lotti sopra soglia con: sintesi,
   punteggio, motivazione, link alla perizia in raw/, link al portale. I lotti
   sotto soglia si archiviano in DB in silenzio (recuperabili, non buttati).

Idempotenza: rilanciare lo stesso giorno non deve produrre doppioni né
re-notificare lotti già inviati.

---

## 4. Fasi di sviluppo (rispettare l'ordine)

**Fase 1 — MVP notifica grezza.** Scraper + DB + Telegram. Trova i lotti nuovi
dei comuni target e li manda su Telegram con titolo/prezzo base/link. NESSUNA
analisi. Deve girare in cron da subito. È il fondamento su cui calibrare il resto.

**Fase 2 — download + OCR.** Recupero automatico della perizia in `raw/`,
estrazione testo, OCR per le scansioni. Ancora nessuno scoring: si verifica solo
che il testo esca pulito.

**Fase 3 — estrazione LLM + scoring.** `extractor.py` + `scorer.py`. La notifica
diventa ricca: dati strutturati + punteggio + motivazione secondo la griglia.

**Fase 4 — rifinitura.** Calcolo automatico del margine di flip (checklist costi),
filtri fini, storico, eventuale dashboard. Solo dopo che le fasi 1-3 sono solide.

Regola: non iniziare una fase se la precedente non gira in produzione sul VPS.

---

## 5. Il gate "segnala o scarta" (anti-illusione)

Mutuato dal gate "scala o scarta" dei progetti di trading. Serve a non annegare
in falsi positivi né a perdere l'affare vero:

- Un lotto si NOTIFICA solo se supera TUTTE le soglie hard della griglia
  (prezzo/valore, zona ammessa, occupazione gestibile, no abusi insanabili).
- Un solo criterio hard mancante → scarto silenzioso, niente notifica.
- Non "ammorbidire" i criteri per far passare più lotti: in asta la disciplina
  è tutto, l'affare arriva a chi aspetta il lotto giusto.
- Se in una settimana non passa nulla, è il comportamento CORRETTO, non un bug.
  (Ma verifica sempre che lo scraper giri — vedi principio §1.4 "fail loud".)

---

## 6. Interfaccia: Telegram vs Claude Code

- **Telegram** = canale di OUTPUT e trigger rapidi. Riceve le notifiche dei lotti.
  Comandi strutturati (`/scan`, `/status`, `/lotto <id>`, `/soglia <param> <val>`).
  Stesso pattern del bot Kraken già in produzione: riusa quel codice.
- **Claude Code** (anche da mobile) = dove si fa il lavoro di ragionamento: modifica
  della griglia, analisi di un lotto specifico in linguaggio libero, manutenzione
  della wiki `research/`, evoluzione del codice.
- Linguaggio libero su Telegram NON è previsto di default (costo LLM per messaggio
  sul VPS). Se in futuro lo si vuole, è una scelta esplicita da annotare qui.

---

## 7. Stack tecnico

- **Runtime**: Python 3.12 su Hetzner CX22, Ubuntu 24.04 (stesso VPS del bot Kraken).
- **Fetch/scrape**: `httpx` + `BeautifulSoup`/`lxml`.
- **OCR**: `pdftoppm` (poppler) + `Tesseract` — pipeline già collaudata sui
  risconti Maint System, riusala.
- **Estrazione strutturata**: API Anthropic (stesso pattern di Chiriba Stat).
  Modello economico per l'estrazione di massa, escalation solo se serve.
- **Stato**: SQLite (`db/aste.sqlite`).
- **Notifiche**: `python-telegram-bot` (codice riusato dal bot Kraken).
- **Scheduling**: cron giornaliero (es. 07:00). Log su file + alert Telegram su fallimento.

---

## 8. Fonti dati (ordine di priorità e stabilità)

1. **Portale Vendite Pubbliche** (pvp.giustizia.it) — ufficiale, copre tutti i
   tribunali, ricerca per comune/tribunale/tipologia. Fonte primaria.
2. **Gestori delle vendite** (Astalegale, Aste Giudiziarie Inlinea, ecc.) —
   spesso pagine più strutturate e perizie più accessibili. Fonte secondaria.

Nota: nessuna API pubblica comoda → scraping HTML. La struttura può cambiare e
rompere lo scraper: isola i selettori in un punto solo (`src/scraper.py`) per
riparare in fretta. Salva sempre l'HTML grezzo in `raw/` per poter ri-parsare
offline senza ri-scaricare.

---

## 9. Metodologia di sviluppo — Superpowers

Questo progetto adotta **Superpowers** (plugin open-source per Claude Code, di
Prime Radiant, disponibile nel marketplace ufficiale) come framework di
disciplina per la scrittura del codice: brainstorming prima di implementare,
TDD red-green-refactor, debugging sistematico, code review con subagent.

### 9.1 Setup — installa se manca

All'inizio della prima sessione di coding, l'agente verifica se Superpowers è
installato e lo installa se assente:

1. Controlla: `claude skill list | grep -i superpowers` (oppure verifica la
   presenza del dispatcher "using superpowers" tra le skill attive).
2. Se NON presente, installalo dal marketplace ufficiale:
   `/plugin install superpowers@claude-plugins-official`
   - Se `/plugin` non è riconosciuto, aggiorna Claude Code
     (`npm update -g @anthropic-ai/claude-code`) e riavvia la sessione.
   - Installazione consigliata **globale** (user-level), così vale anche per
     gli altri progetti dell'utente (bot Kraken, oanda-quant, Chiriba).
3. Verifica l'avvenuta installazione e annota in `research/log.md` versione e data.
4. Se l'installazione fallisce (rete, permessi, marketplace non raggiungibile),
   NON bloccare il lavoro: segnalalo, prosegui applicando manualmente la
   disciplina descritta sotto (§9.3), e riprova l'installazione a sessione nuova.

Nota: Superpowers è di terze parti (MIT), non sviluppato da Anthropic. Ha una
telemetria opzionale disattivabile con `SUPERPOWERS_DISABLE_TELEMETRY=1`;
impostala se l'utente preferisce.

### 9.2 Applicazione SELETTIVA (importante)

Superpowers tende a imporre le sue fasi a tutto. In questo progetto la disciplina
piena va applicata solo dove ripaga, per non rallentare le parti volatili.

**TDD e review piena — OBBLIGATORI su:**
- `scorer.py` — la logica di punteggio è il cuore decisionale: un bug qui
  significa segnalare lotti sbagliati o scartare affari veri. Test prima.
- `extractor.py` — l'estrazione perizia→JSON: usa perizie campione salvate in
  `tests/` come fixture. Un'estrazione errata a valle inquina tutto.
- `parser.py` — logica OCR/testo: testabile con PDF campione.
- Qualsiasi calcolo fiscale/finanziario (margine flip, prezzo-valore): TDD sempre.

**Disciplina alleggerita — brainstorming sì, TDD rigido no, su:**
- `scraper.py` e `downloader.py` — dipendono da HTML esterno instabile: si
  presidiano meglio con fixture HTML salvate in `raw/` e test d'integrazione
  che con TDD puro. Se l'agente vuole "scrivere prima il test che fallisce" su
  una pagina che cambia ogni mese, è tempo sprecato. Usa `--skip` mirati.
- `notifier.py` — thin wrapper su Telegram già collaudato (bot Kraken): test di
  fumo sufficiente.

**Regola pratica:** se un modulo ha logica deterministica e testabile in
isolamento → TDD pieno. Se è I/O verso un servizio esterno volatile → fixture +
integration test, salta il red-green rigido. In dubbio, TDD.

### 9.3 Fallback se Superpowers non è disponibile

Se il plugin non si installa, applica comunque a mano il minimo indispensabile:
1. **Brainstorming** prima di ogni modulo nuovo: spec breve, alternative,
   validazione con l'utente (coerente con §4 "sviluppo a fasi").
2. **Test prima** sui moduli critici della §9.2.
3. **Self-review in due passi** prima di dichiarare fatto: prima "funziona?",
   poi "è pulito/robusto?". Nessun "dovrebbe funzionare" senza prova.
4. **Evidence over claims**: verifica che giri davvero, non affermare che gira.

Questi quattro punti sono l'essenza di Superpowers e valgono anche senza il plugin.

---

## 10. Convenzioni per l'agente

- **Prima di scrivere codice**: leggi `research/index.md` e `research/log.md`.
  La conoscenza di dominio (insidie delle perizie, note sui comuni) vive lì.
- **Dopo ogni sessione produttiva**: appendi a `research/log.md` una riga
  greppabile con data, cosa fatto, cosa imparato. Aggiorna le pagine `research/`
  pertinenti se hai scoperto un pattern nuovo (es. un formato di perizia ostico).
- **Segreti**: mai in chiaro, mai committati. Solo in `config/secrets.env`
  (in `.gitignore`). Se ne vedi uno hardcoded, segnalalo e spostalo.
- **Idempotenza e sicurezza dati**: nessuna operazione deve corrompere `raw/`
  o duplicare notifiche. In caso di dubbio, scrivi su file nuovo, non sovrascrivere.
- **mkdir**: crea le cartelle una per una (`mkdir -p` singoli), l'espansione con
  parentesi graffe può fallire in silenzio in alcuni ambienti.
- **Onestà tecnica**: se un approccio è fragile (es. parsing regex su perizie
  eterogenee), dillo e proponi l'alternativa robusta (LLM), non nasconderlo.

---

## 11. Dominio: cosa deve sapere l'agente sulle aste

Conoscenza minima per non fare danni (dettagli in `research/fiscale.md`):

- **Prezzo-valore**: se uso abitativo (cat. A tranne A/10) e acquisto da persona
  fisica, le imposte si pagano sul valore catastale, non sul prezzo. Vantaggio.
- **Occupazione**: libero = ottimo; occupato dal debitore = liberabile via
  custode/giudice; occupato con contratto opponibile (data certa anteriore al
  pignoramento) = da scartare per uso proprio/turistico.
- **Costi accollati**: arretrati condominiali anno in corso + precedente a carico
  dell'aggiudicatario. Sempre da quantificare col custode.
- **Difformità/abusi**: segnalati in perizia; se insanabili possono affondare
  l'operazione. Criterio hard di scarto.
- **Flip**: plusvalenza su rivendita <5 anni tassata (sostitutiva 26% o IRPEF).
  Margine teorico d'asta ≠ utile netto: vanno sottratti imposte, procedura,
  ristrutturazione, possesso, rivendita.
- **Saldo prezzo**: dovuto in 60-120 giorni dall'aggiudicazione → la liquidità
  deve essere pronta, non "in arrivo".

Questi parametri alimentano la griglia di scoring: l'agente non li reinventa,
li applica come definiti in `config/scoring.yaml` e spiegati in `research/scoring.md`.

---

## 12. Decisioni aperte (da sciogliere con l'utente)

Risolte il 2026-07-05 (dettagli nelle pagine `research/` indicate):

- [x] **Target geografico, non per tribunale** → filtro sull'ubicazione
      dell'immobile: tutta la provincia di Venezia + comune di Treviso + comuni
      TV limitrofi. L'utente è cresciuto a Mestre. (`research/comuni.md`,
      `config/comuni.yaml`)
- [x] **Griglia specializzata sul FLIP** (rivendita <5 anni), non sul reddito.
      (`research/scoring.md`, `config/scoring.yaml`)
- [x] **Modello LLM: Haiku 4.5 + escalation** sui casi difficili.
      (`research/perizie.md`)

- [x] **Parametri Fase 1** (2026-07-05): bot Telegram **dedicato**; comuni TV
      limitrofi tutti attivi (7); cron giornaliero **07:00**; tipologia **solo
      residenziale**. (`research/fase1-mvp-spec.md`, `config/comuni.yaml`)

Ancora aperte:

- [ ] Pesi e soglie esatti della griglia (`config/scoring.yaml`): sconto minimo
      su stima, zone A/B/C, superficie min/max, categorie ammesse.

> Aggiorna questa lista man mano che le decisioni vengono prese, spostando le
> voci risolte nella pagina `research/` pertinente.
