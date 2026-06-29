"""
Category Embedder: classifica una descrizione testuale nella categoria
più semanticamente vicina usando sentence-transformers.

Il modello e gli embedding delle categorie vengono caricati una sola volta
(singleton) per non rallentare l'elaborazione di righe successive.

Modello usato: paraphrase-multilingual-MiniLM-L12-v2
  - ~120MB, supporta italiano nativamente
  - scaricato automaticamente da HuggingFace al primo utilizzo
"""
from __future__ import annotations

from typing import Optional

# Descrizioni arricchite per ogni categoria (senza emoji) per migliorare
# la qualità del matching semantico con testi in italiano e inglese
CATEGORY_DESCRIPTIONS: dict[str, str] = {
    "🏠 Casa": (
        "affitto mutuo casa appartamento bollette utenze elettricità gas acqua "
        "condominio arredamento mobili elettrodomestici riparazioni manutenzione "
        "pulizie tende tappeti ikea leroy merlin brico"
    ),
    "🍲 Spesa": (
        "supermercato alimentari cibo spesa esselunga carrefour lidl conad "
        "md despar unes pam coop iper spesa settimanale generi alimentari "
        "verdura frutta carne pesce"
    ),
    "🚑 Salute": (
        "farmacia medico ospedale medicina salute visita dentista fisioterapia "
        "farmaco pillole integratori analisi laboratorio pediatra specialista "
        "pronto soccorso ambulatorio cure sanitarie"
    ),
    "🚌 Trasporti": (
        "metro autobus tram treno abbonamento trasporto pubblico atm trenitalia "
        "italo biglietto bus navetta pendolare mezzi pubblici "
        "ridemovi monopattino bicicletta sharing"
    ),
    "👕 Vestiario": (
        "abbigliamento vestiti scarpe borsa accessori moda zara h&m muji "
        "calzature giacca pantaloni camicia vestito abito negozio moda "
        "intimo calze maglietta shopping abbigliamento sportivo"
    ),
    "🌿 Cura Personale": (
        "parrucchiere barbiere estetista cosmetici profumo shampoo sapone "
        "igiene personale bellezza trucco salone nail manicure pedicure "
        "cura capelli rasatura depilazione spa trattamento"
    ),
    "🏋️ Sport": (
        "palestra fitness sport abbonamento piscina calcio tennis running "
        "yoga pilates crossfit allenamento attrezzatura sportiva "
        "squadra campionato torneo gara corsa bici"
    ),
    "📚 Formazione": (
        "libro corso università scuola formazione istruzione udemy coursera "
        "lezione tutoraggio esame corsi online master diploma certificazione "
        "abbonamento rivista podcast educazione"
    ),
    "🛠️ Altre Necessità": (
        "hardware ferramenta utensili riparazione fabbro idraulico elettricista "
        "assistenza tecnica ricambio componente strumento lavoro attrezzatura "
        "materiale ufficio cartoleria cancelleria stampante"
    ),
    "💸 Tasse": (
        "tasse imposte tributi irpef iva f24 agenzia entrate comune multa "
        "bollo auto rc auto assicurazione sanzione pagamento obbligatorio "
        "contributi inps previdenza fiscale acconto"
    ),
    "🎫 Abbonamenti": (
        "abbonamento mensile annuale netflix spotify amazon prime disney "
        "streaming musica software saas cloud servizio ricorrente "
        "telefono cellulare tim vodafone wind tre bolletta telefonica"
    ),
    "🛍️ Acquisti Online": (
        "amazon acquisto online e-commerce shop web store ebay zalando "
        "spedizione pacco ordine online pagamento digitale checkout "
        "marketplace aliexpress shein"
    ),
    "🍝 Cibo Fuori": (
        "ristorante pizzeria trattoria osteria bistrot pranzo cena aperitivo "
        "tavola calda sushi poke kebab hamburger fast food pasto fuori "
        "delivery glovo just eat uber eats"
    ),
    "🍨 Spuntino": (
        "bar caffè colazione cappuccino brioche cornetto panino sandwich "
        "snack spuntino pausa caffetteria gelateria yogurt granita "
        "pasticceria merendina bibita succo"
    ),
    "🎁 Regali": (
        "regalo compleanno natale anniversario presente fiori bouquet "
        "fioraio gioielleria profumeria orologio regalo pensiero "
        "pacchetto sorpresa mazzo fiori"
    ),
    "✈️ Vacanze": (
        "vacanza viaggio aereo hotel albergo b&b airbnb prenotazione "
        "booking volo andata ritorno bagaglio escursione tour crociera "
        "resort spiaggia montagna turismo"
    ),
    "💆 Benessere": (
        "massaggio spa benessere relax centro estetico terme sauna bagno "
        "turco meditazione yoga benessere psicologico mindfulness "
        "equilibrio mentale ritiro"
    ),
    "🎳 Uscite Fuori": (
        "uscita sera cinema teatro concerto evento museo mostra discoteca "
        "bar serata pub nightclub locale spettacolo festa bowling "
        "karaoke escape room divertimento"
    ),
    "🎮 Hobby": (
        "hobby videogioco console gioco playstation xbox nintendo steam "
        "modellismo fotografia musica strumento hobby collezionismo "
        "materiale creativo fai da te"
    ),
    "🌟 Trasporti Extra": (
        "taxi uber noleggio auto parcheggio garage autostrada pedaggi "
        "carburante benzina gasolio rifornimento area service revisione "
        "meccanico officina gomme"
    ),
    "📲 Tecnologia": (
        "telefono smartphone tablet computer laptop accessori tech apple "
        "samsung cuffie auricolari caricabatterie cover custodia "
        "elettronica digitale gadget app store google play"
    ),
    "🎲 Altro": (
        "altro spesa generica non classificata varie diversi pagamento "
        "transazione generica bonifico"
    ),
}

_embedder_instance: Optional["CategoryEmbedder"] = None


class CategoryEmbedder:
    """Singleton che carica il modello una volta sola e calcola i match."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        self._np = np
        self._model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        self._categories = list(CATEGORY_DESCRIPTIONS.keys())
        self._category_embeddings = self._model.encode(
            list(CATEGORY_DESCRIPTIONS.values()),
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    def classify(self, text: str, threshold: float = 0.20) -> str:
        """
        Ritorna la categoria più vicina semanticamente al testo.
        Se il punteggio massimo è sotto `threshold`, ritorna '🎲 Altro'.
        """
        if not text or not text.strip():
            return "🎲 Altro"

        query_emb = self._model.encode(
            [text.strip()],
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        scores = self._np.dot(self._category_embeddings, query_emb[0])
        best_idx = int(self._np.argmax(scores))
        best_score = float(scores[best_idx])

        if best_score < threshold:
            return "🎲 Altro"
        return self._categories[best_idx]


def get_embedder() -> CategoryEmbedder:
    """Ritorna l'istanza singleton del CategoryEmbedder (lazy init)."""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = CategoryEmbedder()
    return _embedder_instance
