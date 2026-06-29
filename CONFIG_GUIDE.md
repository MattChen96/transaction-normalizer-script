# CONFIG_GUIDE — Come scrivere un `config.json` per una nuova sorgente

Questa guida è pensata per essere passata a un agente AI. Contiene tutto il necessario per creare un `sources/<nome_banca>/config.json` corretto e funzionante, senza leggere il documento di design completo.

---

## 1. Struttura della cartella sorgente

```
sources/
└── <nome_banca>/          ← identificatore canonico (lowercase, underscore)
    ├── config.json        ← configurazione completa (questo file)
    └── sample.csv         ← 10–20 righe rappresentative del CSV/XLSX reale
```

Il nome della cartella (es. `n26`, `fineco`, `satispay`) viene usato dal sistema per:
- il source detection automatico per nome file
- il valore predefinito del campo `Conto` nell'output

---

## 2. Struttura di primo livello di `config.json`

```json
{
  "source": { ... },
  "file": { ... },
  "filters": { ... },
  "fields": { ... }
}
```

Tutte e quattro le chiavi sono supportate. `filters` è opzionale; `source`, `file`, `fields` sono obbligatorie.

---

## 3. Sezione `source`

```json
"source": {
  "name": "N26",
  "version": "1.0",
  "description": "Export CSV N26 — formato europeo"
}
```

- `name` (obbligatorio): nome display usato nei log e nel campo `Conto` se non mappato esplicitamente
- `version` (raccomandato): stringa libera per tracciabilità
- `description` (opzionale)

---

## 4. Sezione `file`

Descrive come leggere fisicamente il file grezzo.

```json
"file": {
  "format": "csv",
  "encoding": "utf-8",
  "delimiter": ",",
  "skip_rows": 0,
  "header_row": 0,
  "decimal_separator": ".",
  "thousands_separator": ""
}
```

| Chiave | Default | Note |
|---|---|---|
| `format` | — | **Obbligatorio.** `"csv"`, `"xlsx"`, o `"xls"` |
| `encoding` | `"utf-8"` | Usare `"utf-8-sig"` per file con BOM (comuni su Windows/Excel) |
| `delimiter` | `","` | Solo per CSV. Usare `";"` per formato europeo, `"\t"` per TSV |
| `skip_rows` | `0` | Righe da saltare prima dell'header (es. `3` per file Excel con titolo) |
| `header_row` | `0` | Indice 0-based della riga header dopo il salto |
| `sheet_name` | `0` | Solo per Excel. Nome del foglio (`"Movimenti"`) o indice numerico |
| `decimal_separator` | `"."` | `","` per formato italiano/europeo |
| `thousands_separator` | `""` | `"."` per formato italiano (es. `1.234,56`) |
| `quotechar` | `"\""` | Solo per CSV |

---

## 5. Sezione `filters`

Filtra le righe **prima** del mapping, sui dati grezzi. Opzionale.

```json
"filters": {
  "include": [
    { "column": "Stato", "operator": "equals", "value": "COMPLETATO" }
  ],
  "exclude": [
    { "column": "Tipo", "operator": "in", "value": ["Storno", "Rettifica"] },
    { "column": "Importo", "operator": "equals", "value": "0" }
  ]
}
```

**Semantica:**
- `include` → AND logico: la riga passa **solo se tutte** le regole include sono vere
- `exclude` → OR logico: la riga viene scartata **se almeno una** regola exclude è vera
- Se `include` è assente/vuoto, tutte le righe passano
- Se `exclude` è assente/vuoto, nessuna riga viene scartata

**Struttura di una regola:**
```json
{
  "column": "<nome colonna input>",
  "operator": "<operatore>",
  "value": "<valore>",
  "case_sensitive": false
}
```

**Operatori disponibili:**

| Operatore | `value` richiesto | Descrizione |
|---|---|---|
| `equals` | scalar | Uguaglianza esatta |
| `not_equals` | scalar | Diverso da |
| `in` | array | La cella è nella lista |
| `not_in` | array | La cella non è nella lista |
| `contains` | string | Contiene la sottostringa |
| `not_contains` | string | Non contiene la sottostringa |
| `starts_with` | string | Inizia con |
| `ends_with` | string | Termina con |
| `regex` | string (pattern) | Soddisfa la regex |
| `gt` / `gte` / `lt` / `lte` | numeric | Confronto numerico |
| `is_empty` | — | Cella vuota |
| `is_not_empty` | — | Cella non vuota |

---

## 6. Sezione `fields`

**Principio fondamentale:** il mapping è orientato all'output. Le chiavi sono sempre i 7 campi di output, non i nomi delle colonne di input.

```json
"fields": {
  "Data":        { ... },
  "Acquisto":    { ... },
  "Importo":     { ... },
  "Categoria":   { ... },
  "Tag":         { ... },
  "Wallet":      { ... },
  "Note":        { ... }
}
```

Tutti e 7 i campi sono obbligatori. Per ogni campo si può usare una di queste strategie:

### 6a. Valore costante

```json
"Wallet": { "constant": "Hype" }
"Tag": { "constant": "" }
```

### 6b. Lettura da una colonna

```json
"Data": {
  "input_column": "Transaction Date",
  "transform": [ ... ]
}
"Acquisto": {
  "input_column": "Description",
  "transform": [ { "type": "trim" } ]
}
```

### 6c. Concatenazione di più colonne

```json
"Acquisto": {
  "input_columns": ["Merchant", "Category"],
  "concat_separator": " — ",
  "transform": [ { "type": "trim" } ]
}
```

### 6d. Fallback

```json
"Wallet": {
  "input_column": "PaymentMethod",
  "transform": [ { "type": "trim" } ],
  "default": "Contanti"
}
```

---

## 7. Transform pipeline

Lista ordinata di trasformazioni applicate in sequenza al valore del campo.

```json
"transform": [
  { "type": "trim" },
  { "type": "date_format", "input_format": "%d/%m/%Y", "output_format": "%Y-%m-%d" }
]
```

### Catalogo completo

**Testo:**
| `type` | Parametri | Descrizione |
|---|---|---|
| `trim` | — | Rimuove spazi iniziali/finali |
| `lowercase` | — | Converte in minuscolo |
| `uppercase` | — | Converte in maiuscolo |
| `titlecase` | — | Prima lettera maiuscola per parola |
| `replace` | `find`, `replacement` | Sostituisce sottostringa esatta |
| `replace_map` | `map: {chiave: valore}` | Sostituisce valore esatto via dizionario |
| `strip_chars` | `chars` | Rimuove i caratteri specificati da inizio/fine |
| `regex_replace` | `pattern`, `replacement` | Sostituzione regex |
| `regex_extract` | `pattern`, `group` (default 1) | Estrae un gruppo dalla regex |
| `split_take` | `separator`, `index` | Divide e prende l'elemento all'indice |

**Date:**
| `type` | Parametri | Descrizione |
|---|---|---|
| `date_format` | `input_format` (strftime), `output_format` (default `%Y-%m-%d`) | Conversione formato data |

Formati comuni: `%d/%m/%Y` (IT), `%d.%m.%Y` (DE), `%Y-%m-%d %H:%M:%S` (ISO con orario), `%b %d, %Y` (EN mese abbreviato)

**Numeri:**
| `type` | Parametri | Descrizione |
|---|---|---|
| `number_normalize` | `decimal_separator`, `thousands_separator` | Converte numero locale a stringa con punto decimale |
| `number_abs` | — | Valore assoluto |
| `number_negate` | — | Inverte il segno |
| `number_round` | `decimals` (default 2) | Arrotonda a N cifre |

**Avanzate:**
| `type` | Parametri | Descrizione |
|---|---|---|
| `concat` | `values: [...]`, `separator` | Concatena valori statici o `"$NomeColonna"` |
| `coalesce` | `columns: [...]` | Primo valore non-vuoto tra le colonne |
| `sign_from_column` | `column`, `positive_values: [...]`, `negative_values: [...]` | Determina il segno dell'importo da una colonna indicatrice |
| `conditional` | `conditions: [...]`, `else` | If/else dichiarativo (vedi §8) |

---

## 8. Trasformazione `conditional`

Usata per determinare `Tipo` (ENTRATA/USCITA/TRASFERIMENTO) o per mappare valori in base a logica condizionale.

```json
{
  "type": "conditional",
  "conditions": [
    {
      "if_column": "Tipo movimento",
      "operator": "equals",
      "value": "Bonifico in uscita",
      "then": "TRASFERIMENTO"
    },
    {
      "if_column": "Importo",
      "operator": "gt",
      "value": "0",
      "then": "ENTRATA"
    }
  ],
  "else": "USCITA"
}
```

- `if_column`: nome di una **colonna di input** (non di output)
- `operator`: stesso set di operatori dei filtri
- `then`: valore da restituire se la condizione è vera
- `else`: valore da restituire se nessuna condizione è vera (`null` → stringa vuota)
- Le condizioni sono valutate nell'ordine; vince la prima vera

---

## 9. Category Mapping

Usato tipicamente per il campo `Categoria`. Traduce i valori grezzi della banca in categorie standard.

```json
"Categoria": {
  "input_column": "Category",
  "transform": [
    { "type": "trim" },
    { "type": "lowercase" }
  ],
  "category_mapping": {
    "map": {
      "groceries":  "Supermercato",
      "eating out": "Ristoranti",
      "transport":  "Trasporti",
      "shopping":   "Shopping"
    },
    "case_sensitive": false,
    "default": "Altro"
  }
}
```

- `map`: dizionario `valore_grezzo → categoria_standard`
- `default` (**obbligatorio**): categoria di fallback per valori non presenti nel `map`
- `case_sensitive` (default `false`): se `true`, il lookup è case-sensitive
- `trim_before_match` (default `true`): se applicare trim prima del lookup

Se è presente sia `transform` che `category_mapping`, prima si applica la pipeline transform, poi il lookup. Utile per fare `lowercase` prima del match.

---

## 10. Schemi ricorrenti

### CSV europeo con separatore `;` e formato data `DD.MM.YYYY`
```json
"file": {
  "format": "csv",
  "encoding": "utf-8-sig",
  "delimiter": ";",
  "decimal_separator": ",",
  "thousands_separator": "."
}
```
```json
"Data": {
  "input_column": "Datum",
  "transform": [
    { "type": "trim" },
    { "type": "date_format", "input_format": "%d.%m.%Y" }
  ]
}
```

### Excel con righe di intestazione da saltare
```json
"file": {
  "format": "xlsx",
  "skip_rows": 3,
  "header_row": 0,
  "sheet_name": "Movimenti"
}
```

### Importo con simbolo valuta da rimuovere
```json
"Importo": {
  "input_column": "Amount",
  "transform": [
    { "type": "trim" },
    { "type": "regex_replace", "pattern": "[^0-9,\\.\\-]", "replacement": "" },
    { "type": "number_normalize", "decimal_separator": ",", "thousands_separator": "." },
    { "type": "number_round", "decimals": 2 }
  ]
}
```

### Importo con colonna separata per il segno
```json
"Importo": {
  "input_column": "Valore",
  "transform": [
    { "type": "trim" },
    { "type": "number_normalize", "decimal_separator": ",", "thousands_separator": "." },
    {
      "type": "sign_from_column",
      "column": "Tipo",
      "positive_values": ["Accredito", "Entrata"],
      "negative_values": ["Addebito", "Uscita"]
    },
    { "type": "number_round", "decimals": 2 }
  ]
}
```

### Campo `Categoria` mappato da category_mapping
```json
"Categoria": {
  "input_column": "Type",
  "transform": [ { "type": "trim" }, { "type": "lowercase" } ],
  "category_mapping": {
    "map": {
      "groceries":  "🍲 Spesa",
      "restaurant": "🍝 Cibo Fuori",
      "transport":  "🚌 Trasporti",
      "shopping":   "🛍️ Acquisti Online"
    },
    "case_sensitive": false,
    "default": "🎲 Altro"
  }
}
```

### Wallet costante o da colonna
```json
"Wallet": {
  "constant": "Revolut"
}
```
O se proviene da una colonna:
```json
"Wallet": {
  "input_column": "Account",
  "transform": [ { "type": "trim" } ],
  "default": "Contanti"
}
```

---

## 11. Vincoli da rispettare

| Vincolo | Dettaglio |
|---|---|
| 7 campi obbligatori | `fields` deve contenere esattamente: `Data`, `Acquisto`, `Importo`, `Categoria`, `Tag`, `Wallet`, `Note` |
| `category_mapping.default` obbligatorio | Se è presente `category_mapping`, il campo `default` è obbligatorio |
| `input_columns` richiede `concat_separator` | Se si usa `input_columns`, `concat_separator` (anche `""`) deve essere presente |
| Output `Data` → ISO 8601 | Il transform deve produrre `YYYY-MM-DD` |
| Output `Importo` → numero con punto | Negativo = uscita, positivo = entrata |
| Output `Categoria` → enum | Valori validi: 🏠 Casa, 🍲 Spesa, 🚑 Salute, ..., 🎲 Altro |
| Output `Wallet` → enum | Valori validi: Hype, Revolut, Contanti, Satispay, Sella, Trade Republic |

---

## 12. Comandi utili

```bash
# Validare la struttura di un config senza elaborare dati reali
python3 -m src.main --validate-only sources/<nome_banca>/

# Eseguire il pipeline ETL completo
python3 -m src.main

# Testare con una cartella input specifica
python3 -m src.main --input-dir /path/to/input/
```
