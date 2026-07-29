"""
Compare two text files using TF-IDF cosine similarity via scikit-learn.

Uses sklearn's TfidfVectorizer to build weighted vectors and
cosine_similarity to score them.
Top terms can optionally be ranked by log-odds ratio instead of TF-IDF,
which is more reliable when comparing only two documents.

Usage:
    python compare_files.py <file1> <file2> [--top N] [--csv PATH] [--log-odds] [--bigrams]

Options:
    --top N      Number of top terms to show per file (default: 10)
    --csv PATH   Write top terms to a CSV file at PATH
    --log-odds   Rank top terms by log-odds ratio instead of TF-IDF weight
    --bigrams    Include two-word phrases (bigrams) alongside single words
    --english-only       Discard tokens not in the NLTK WordNet English lexicon
    --no-proper-nouns    Remove proper nouns using spaCy POS tagging

Install dependency:
    pip install scikit-learn

Authorship:
    This code was developed with Claude Sonnet 4.6 and reviewed by Alex Diaz-Papkovich.
"""

import sys
import csv
import math
import argparse
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity
from utils import STOP_WORDS, load_text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def interpret(score: float) -> str:
    """Return a human-readable interpretation of the similarity score."""
    if score >= 0.90:
        return "Nearly identical"
    elif score >= 0.70:
        return "Highly similar"
    elif score >= 0.50:
        return "Moderately similar"
    elif score >= 0.25:
        return "Slightly similar"
    else:
        return "Very different"


def top_terms(
    tfidf_row: np.ndarray,
    feature_names: np.ndarray,
    n: int,
) -> list[tuple[str, float]]:
    """Return the N terms with the highest TF-IDF scores for one document."""
    scores = tfidf_row.toarray().flatten()
    indices = np.argsort(scores)[::-1][:n]
    return [(feature_names[i], scores[i]) for i in indices if scores[i] > 0]


def log_odds_terms(
    tokens1: list[str],
    tokens2: list[str],
    stop_words: list[str],
    n: int,
    use_bigrams: bool = False,
) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
    """
    Rank terms by log-odds ratio, returning the top N for each document.

    Log-odds directly compares relative word frequencies between the two
    documents, making it naturally contrastive: a word scoring highly for
    file 1 must appear proportionally more in file 1 than file 2.

    A small Laplace smoothing constant (alpha) is added to every count to
    avoid log(0) for words absent from one document.

    When use_bigrams is True, two-word phrases are added to the token
    stream alongside single words.
    """
    from collections import Counter

    alpha = 0.5  # Laplace smoothing

    stop_set = set(stop_words)

    def make_ngrams(tokens: list[str]) -> list[str]:
        unigrams = [t for t in tokens if t not in stop_set]
        if not use_bigrams:
            return unigrams
        bigrams = [
            f"{tokens[i]} {tokens[i+1]}"
            for i in range(len(tokens) - 1)
            if tokens[i] not in stop_set and tokens[i+1] not in stop_set
        ]
        return unigrams + bigrams

    ngrams1 = make_ngrams(tokens1)
    ngrams2 = make_ngrams(tokens2)

    counts1 = Counter(ngrams1)
    counts2 = Counter(ngrams2)
    vocab = set(counts1) | set(counts2)

    total1 = sum(counts1.values())
    total2 = sum(counts2.values())

    log_odds: dict[str, float] = {}
    for word in vocab:
        freq1 = (counts1.get(word, 0) + alpha) / (total1 + alpha * len(vocab))
        freq2 = (counts2.get(word, 0) + alpha) / (total2 + alpha * len(vocab))
        log_odds[word] = math.log(freq1 / (1 - freq1)) - math.log(freq2 / (1 - freq2))

    # Positive log-odds → distinctive for doc1; negative → distinctive for doc2
    sorted_words = sorted(log_odds.items(), key=lambda x: x[1], reverse=True)
    terms1 = [(w, s) for w, s in sorted_words[:n]]
    terms2 = [(w, abs(s)) for w, s in sorted_words[-n:][::-1]]
    return terms1, terms2


def print_top_terms(label: str, terms: list[tuple[str, float]]) -> None:
    """Pretty-print a ranked list of distinctive terms."""
    print(f"  Top terms in {label}:")
    for rank, (term, score) in enumerate(terms, start=1):
        print(f"    {rank:>2}. {term:<20} {score:.4f}")


def write_csv(
    path: str,
    path1: str,
    terms1: list[tuple[str, float]],
    path2: str,
    terms2: list[tuple[str, float]],
    weight_col: str = "tfidf_weight",
) -> None:
    """Write top terms for both files to a CSV with columns: file, rank, term, <weight_col>."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file", "rank", "term", weight_col])
        for rank, (term, score) in enumerate(terms1, start=1):
            writer.writerow([path1, rank, term, f"{score:.6f}"])
        for rank, (term, score) in enumerate(terms2, start=1):
            writer.writerow([path2, rank, term, f"{score:.6f}"])
    print(f"  CSV written to: {path}")


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def compare_files(
    path1: str,
    path2: str,
    top_n: int = 10,
    csv_path: str | None = None,
    use_log_odds: bool = False,
    use_bigrams: bool = False,
    english_only: bool = False,
    remove_proper_nouns: bool = False,
) -> None:
    """Load files, vectorize with TfidfVectorizer, and compute cosine similarity."""
    # ── Load ──────────────────────────────────────────────────────────────
    text1 = load_text(path1, english_only=english_only, remove_proper_nouns=remove_proper_nouns)
    text2 = load_text(path2, english_only=english_only, remove_proper_nouns=remove_proper_nouns)

    if not text1.strip() or not text2.strip():
        print("Error: one or both files are empty.")
        sys.exit(1)

    # ── Stop words ────────────────────────────────────────────────────────
    # Imported from utils.py — edit CUSTOM_STOP_WORDS there to add your own.
    stop_words: list[str] = STOP_WORDS

    # ── Vectorize ─────────────────────────────────────────────────────────
    ngram_range = (1, 2) if use_bigrams else (1, 1)

    vectorizer = TfidfVectorizer(
        strip_accents="unicode",      # normalise accented characters
        lowercase=True,               # case-insensitive matching
        token_pattern=r"\b[a-z]+\b", # words only, no digits/punctuation
        stop_words=stop_words,        # English built-ins + custom additions
        ngram_range=ngram_range,      # (1,1) unigrams only; (1,2) adds bigrams
        smooth_idf=True,              # IDF = log((1+N)/(1+df)) + 1
        sublinear_tf=True,            # TF = 1 + log(tf), dampens high-frequency terms
        norm="l2",                    # L2-normalise each vector (unit vectors)
    )

    # Fit on both documents so the vocabulary and IDF are shared
    tfidf_matrix = vectorizer.fit_transform([text1, text2])
    feature_names = np.array(vectorizer.get_feature_names_out())

    vec1 = tfidf_matrix[0]  # sparse row vector for file 1
    vec2 = tfidf_matrix[1]  # sparse row vector for file 2

    # ── Cosine similarity ─────────────────────────────────────────────────
    score = cosine_similarity(vec1, vec2)[0][0]

    # ── Word counts ───────────────────────────────────────────────────────
    analyzer = vectorizer.build_analyzer()
    words1 = set(analyzer(text1))
    words2 = set(analyzer(text2))
    vocab  = feature_names.tolist()

    # ── Top terms ─────────────────────────────────────────────────────────
    if use_log_odds:
        tokens1 = analyzer(text1)
        tokens2 = analyzer(text2)
        terms1, terms2 = log_odds_terms(tokens1, tokens2, stop_words, top_n, use_bigrams)
        weight_col = "log_odds"
        ranking_label = "log-odds ratio"
    else:
        terms1 = top_terms(vec1, feature_names, top_n)
        terms2 = top_terms(vec2, feature_names, top_n)
        weight_col = "tfidf_weight"
        ranking_label = "TF-IDF weight"

    ngrams_label = "unigrams + bigrams" if use_bigrams else "unigrams only"

    # ── Report ────────────────────────────────────────────────────────────
    W = 42
    print("=" * W)
    print(" File Comparison Report (sklearn TF-IDF)")
    print("=" * W)
    print(f"  File 1 : {path1}")
    print(f"  File 2 : {path2}")
    print("-" * W)
    print(f"  {'Unique words – File 1':<26} {len(words1):>6}")
    print(f"  {'Unique words – File 2':<26} {len(words2):>6}")
    print(f"  {'Shared words':<26} {len(words1 & words2):>6}")
    print(f"  {'Combined vocabulary':<26} {len(vocab):>6}")
    print(f"  {'Stop words (EN + custom)':<26} {len(stop_words):>6}")
    print("-" * W)
    print(f"  {'TF-IDF cosine similarity':<26} {score:.4f}  ({score*100:.1f}%)")
    print(f"  {'Interpretation':<26} {interpret(score)}")
    print(f"  {'Top terms ranked by':<26} {ranking_label}")
    print(f"  {'N-gram range':<26} {ngrams_label}")
    print("-" * W)
    print_top_terms(f"File 1 ({path1})", terms1)
    print()
    print_top_terms(f"File 2 ({path2})", terms2)
    print("=" * W)

    if csv_path:
        write_csv(csv_path, path1, terms1, path2, terms2, weight_col=weight_col)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compare two text files with sklearn TF-IDF cosine similarity."
    )
    parser.add_argument("file1", help="Path to the first text file")
    parser.add_argument("file2", help="Path to the second text file")
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of top TF-IDF terms to display per file (default: 10)",
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        default=None,
        help="Write top terms to a CSV file at PATH",
    )
    parser.add_argument(
        "--log-odds",
        action="store_true",
        default=False,
        help="Rank top terms by log-odds ratio instead of TF-IDF weight",
    )
    parser.add_argument(
        "--bigrams",
        action="store_true",
        default=False,
        help="Include two-word phrases (bigrams) alongside single words",
    )
    parser.add_argument(
        "--english-only",
        action="store_true",
        default=False,
        help="Discard tokens not found in the NLTK WordNet English lexicon",
    )
    parser.add_argument(
        "--no-proper-nouns",
        action="store_true",
        default=False,
        help="Remove proper nouns using spaCy POS tagging",
    )
    args = parser.parse_args()
    compare_files(
        args.file1, args.file2,
        top_n=args.top,
        csv_path=args.csv,
        use_log_odds=args.log_odds,
        use_bigrams=args.bigrams,
        english_only=args.english_only,
        remove_proper_nouns=args.no_proper_nouns,
    )