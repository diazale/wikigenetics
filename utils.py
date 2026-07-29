"""
Utilities for compare_files.py

Some of these were developed for a BERTopic clustering approach, which was ultimately abandoned.

Dependencies:
    pip install scikit-learn spacy nltk
    python -m spacy download en_core_web_sm
    python -c "import nltk; nltk.download('wordnet')"

Authorship
- Alex Diaz-Papkovich
- Developed with Claude Sonnet 4.6
"""

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS


# ---------------------------------------------------------------------------
# Stop words
# ---------------------------------------------------------------------------

# Edit this list to add any domain-specific words you want to exclude.
# These are merged with sklearn's built-in English stop word list.
CUSTOM_STOP_WORDS: list[str] = [
    "also",
    "may",
    "one",
    "use",
    "used",
    "using",
    "said",
    "redirect","amid","like","post","despite","compromising","file","pp","p","came","vol",
    "usually","various","called","retrieved","ed","refer","et","com","come","quite","took",
    "went","greatly","furthermore","approximately"
]

# Pre-built combined stop word list (list, as TfidfVectorizer requires)
STOP_WORDS: list[str] = list(ENGLISH_STOP_WORDS.union(CUSTOM_STOP_WORDS))


# ---------------------------------------------------------------------------
# Lazy singletons -- loaded once on first use
# ---------------------------------------------------------------------------

_wordnet_words: set[str] | None = None
_nlp = None


def _get_wordnet_words() -> set[str]:
    """Return the set of all lowercase WordNet lemma names (loaded once)."""
    global _wordnet_words
    if _wordnet_words is None:
        try:
            from nltk.corpus import wordnet as wn
            _wordnet_words = set(wn.words())
        except LookupError:
            import nltk
            print("Downloading NLTK WordNet data...")
            nltk.download("wordnet", quiet=True)
            from nltk.corpus import wordnet as wn
            _wordnet_words = set(wn.words())
    return _wordnet_words


def _get_nlp():
    """Return the spaCy model (loaded once, with only the tagger enabled)."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        except OSError:
            raise OSError(
                "spaCy model 'en_core_web_sm' not found. "
                "Install it with: python -m spacy download en_core_web_sm"
            )
    return _nlp


# ---------------------------------------------------------------------------
# Text filters
# ---------------------------------------------------------------------------

def filter_english_words(text: str) -> str:
    """
    Remove tokens not found in the NLTK WordNet English lexicon.

    Non-English words, numbers, and terms absent from WordNet are dropped.
    Lookups are case-insensitive. Highly technical or domain-specific terms
    absent from WordNet will also be removed -- this is an acceptable
    tradeoff for most general-purpose use cases.
    """
    english_words = _get_wordnet_words()
    tokens = text.split()
    return " ".join(t for t in tokens if t.lower() in english_words)


def filter_proper_nouns(text: str) -> str:
    """
    Remove proper nouns using spaCy part-of-speech tagging.

    Processes the text in chunks to avoid exceeding spaCy's max_length limit
    on very large documents. Only the tagger is run (NER and parser are
    disabled) for speed. Tokens tagged PROPN are dropped; all others are kept.
    """
    nlp = _get_nlp()
    chunk_size = 10_000  # words per chunk -- safe for spaCy's char limit
    words = text.split()

    if len(words) <= chunk_size:
        doc = nlp(text)
        return " ".join(token.text for token in doc if token.pos_ != "PROPN")

    result: list[str] = []
    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i : i + chunk_size])
        doc = nlp(chunk)
        result.extend(token.text for token in doc if token.pos_ != "PROPN")
    return " ".join(result)


def preprocess(
    text: str,
    english_only: bool = True,
    remove_proper_nouns: bool = True,
) -> str:
    """
    Apply configured text filters in the correct order.

    Proper noun removal runs first (requires original casing for accurate
    POS tagging), followed by English-word filtering on the cleaned stream.
    """
    if remove_proper_nouns:
        text = filter_proper_nouns(text)
    if english_only:
        text = filter_english_words(text)
    return text


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_text(
    filepath: str,
    english_only: bool = False,
    remove_proper_nouns: bool = False,
) -> str:
    """
    Read a text file, strip Category: lines, and apply optional filters.

    Filters default to False so existing callers are unaffected when the
    flags are not passed. Enable them via --english-only and
    --no-proper-nouns in each script's CLI.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    text = "".join(line for line in lines if not line.startswith("Category:"))

    if english_only or remove_proper_nouns:
        text = preprocess(
            text,
            english_only=english_only,
            remove_proper_nouns=remove_proper_nouns,
        )
    return text