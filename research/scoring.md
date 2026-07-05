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

## Pesi soft — perché

DA DECIDERE con l'utente (§12). Domanda a monte non ancora sciolta: la griglia
serve **investimento a reddito**, **flip**, o entrambi? Cambia i pesi (rendita vs
margine di rivendita). Vedi `fiscale.md` per la differenza fra margine teorico
d'asta e utile netto.

## Decisioni aperte tracciate qui

- [ ] Sconto minimo su stima (numero).
- [ ] Zone ammesse (A/B/C) — dipende da `comuni.md`.
- [ ] Categorie catastali ammesse.
- [ ] Superficie min/max.
- [ ] Pesi soft e soglia di notifica.
- [ ] Reddito vs flip: una griglia o due profili?
