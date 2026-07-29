"""
Seeded terminology categorization for a corpus of paragraphs.

Given a set of predefined terminology categories — each a list of terms —
this script scans every paragraph in the corpus and records which category
terms appear, how often, and where. Paragraphs are multi-label: a single
paragraph can match several categories simultaneously.

This is a transparent, auditable, dictionary-based method. Unlike topic
modelling, every assignment can be traced back to the exact term that
triggered it, which matters when the analysis concerns sensitive subject
matter and results need to be defensible and spot-checkable.

While there are default categories built into the script, we used our own
custom JSONs, which are provided in the repository.

Usage:
    python seeded_terminology.py <input> [options]

Arguments:
    input               Directory of .txt files, or a manifest .txt file
                        where each line is a path to a document. Each file
                        is one document containing multiple paragraphs
                        separated by newlines; every non-empty paragraph
                        becomes its own corpus unit.

Options:
    --csv PATH          Per-paragraph category counts (default: term_counts.csv)
    --summary PATH      Corpus-level summary report (default: term_summary.txt)
    --categories PATH   JSON file overriding the default category definitions
    --min-count N       Only assign a category if its total term hits in a
                        paragraph is >= N (default: 1)

No third-party dependencies required — standard library only.

Authorship:
    This code was written with Claude Opus 4.8 and reviewed by Alex Diaz-Papkovich.
"""

import re
import sys
import csv
import json
import argparse
from pathlib import Path
from collections import defaultdict, Counter


# ---------------------------------------------------------------------------
# Default category definitions
# ---------------------------------------------------------------------------
#
# Each category maps to a list of terms. Terms may be single words
# ("haplogroup") or multi-word phrases ("allele frequency"). Matching is
# case-insensitive and respects word boundaries, so "cluster" will not match
# inside "blockbuster". Edit freely or override with a JSON file via
# --categories.
#
# The goal is descriptive: to record WHICH specialized vocabulary appears in
# the text, as a way of characterizing how the text is written. Counts
# describe the text, not the populations the text discusses.
#
# Categories distinguish technical method vocabulary (population_genetics_
# methods, statistical_clustering) from substantive subject vocabulary
# (ancestry, phenotype, health, comparison, subsistence, mixing). Because
# this is multi-label, a few terms intentionally appear in more than one
# category where they carry two senses — e.g. "gene flow" and "introgression"
# are both a method and a description of mixing, and "divergence" is both a
# phylogenetic term and an origins term. This overlap is expected; it is a
# real property of how the vocabulary is used.

DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "population_genetics_methods": [
        "haplogroup", "macrohaplogroup", "haplotype", "allele",
        "allele frequency", "snp", "single nucleotide polymorphism",
        "introgression", "genetic marker", "uniparental marker", "uniparental",
        "microsatellite", "mtdna", "mitochondrial dna", "y-chromosome",
        "y chromosome", "y-dna", "autosomal", "linkage disequilibrium",
        "fst", "coalescent", "phylogenetic", "phylogeny", "archaeogenetic",
        "archaeogenetics", "ancient dna", "adna", "genome", "sequenced genome",
        "genetic distance", "genetic affinity", "genetic affinities",
        "identity by descent", "ibd", "genetic drift", "cline", "clinal",
        "autochthonous", "pleistocene", "genome-wide", "gwas",
        "genome-wide association study", "recombination", "pseudoautosomal",
        "microarray", "snp microarray", "heterozygosity", "heterozygocity",
        "homozygosity", "genetic signature", "genetic structure",
        "clade", "cladal", "sister clade", "bifurcation", "mitogenome",
        "mitogenomes", "polymorphism", "polymorphisms", "allele sharing",
        "y-str", "str loci", "str markers", "short tandem repeat", "loci",
        "bi-allelic", "biallelic", "subclade", "sub-clade", "derived allele",
        "basal", "qpadm", "qpgraph", "f3-statistic", "f4-statistic",
        "d-statistic", "outgroup",
        "haplogroups", "haplotypes", "chromosomes", "y-chromosomes",
        "y-chromosomal", "y-haplogroup", "mtdnas", "markers", "lineages",
        "clades", "subclades", "genomes", "genomic", "snps", "str", "strs",
        "geneticist", "geneticists",
    ],
    "statistical_clustering": [
        "cluster", "clusters", "clustering", "principal component", "pca",
        "k-means", "structure analysis", "dimensionality reduction",
        "distance matrix", "dendrogram", "correlation", "variance",
        "statistically significant", "p-value", "confidence interval",
    ],
    "ancestry_and_origins": [
        "ancestry", "ancestral", "descent", "descended", "lineage", "origin",
        "origins", "migration", "out of africa", "founder population",
        "common ancestor", "peopling", "settlement", "diaspora", "homeland",
        "expansion", "diverge", "diverged", "divergence", "separation time",
        "split", "source population", "ancestral source", "continuity",
        "genetic continuity", "population continuity", "proportion of ancestry",
        "ancestry proportion", "steppe ancestry", "steppe-related",
        "colonist", "colonists", "neolithic", "bronze age", "iron age",
        "stone age", "chalcolithic", "natufian", "demic diffusion",
        "ethnogenesis", "gene pool", "genetic substrate", "substrate",
        "paleolithic", "upper paleolithic", "holocene", "dispersal",
        "southern route dispersal", "most recent common ancestor",
        "last common ancestry",
        # Plural/variant forms frequent in both eras
        "lineages", "migrations", "migrated", "ancestors", "descendants",
        "divergent", "diverging",
    ],
    "phenotype_physical": [
        "phenotype", "phenotypic", "skin color", "skin colour",
        "pigmentation", "stature", "height", "craniofacial", "morphology",
        "physical characteristic", "physical trait", "hair texture",
        "facial feature", "body type",
    ],
    "medical_genetics": [
        "disease", "disorder", "prevalence", "susceptibility", "susceptible",
        "risk allele", "heritability", "carrier", "mutation", "pathogenic",
        "clinical", "morbidity", "mortality", "predisposition",
        "genetic disease", "genetic disorder", "genetic counseling",
        "genetic counselling", "genetic testing", "genetic screening",
        "screening", "ascertainment bias", "colon cancer", "breast cancer",
        "tay-sachs", "tay sachs", "neurological disease", "epidemiology",
        "genetic epidemiology", "founder mutation", "recessive", "dominant allele",
        "at-risk", "increased risk", "homozygosity", "inherited disease",
    ],
    "group_comparison": [
        "differ", "difference", "differences", "differentiated",
        "least differentiated", "similar", "similarity", "similarities",
        "compared to", "in contrast", "distinct", "distinct from",
        "closely related", "genetically closest", "genetically close",
        "resemble", "resembled", "overlap", "homogeneous",
        "genetically homogeneous", "shared", "shared ancestry", "distinguish",
        "isolation", "isolated",
    ],
    "subsistence_mode": [
        "hunter-gatherer", "hunter-gatherers", "forager", "foragers",
        "agriculturalist", "agriculturalists", "farmer", "farmers",
        "pastoralist", "pastoralists", "herder", "herders",
        "subsistence", "foraging", "agriculture", "farming", "early farming",
    ],
    "admixture_and_mixing": [
        "admixture", "admixed", "admixture model", "gene flow", "introgression",
        "assimilated", "assimilation", "displaced", "displacement",
        "diluted", "dilution", "intermarriage", "intermarried", "interbreeding",
        "mixed", "mixing", "enriched", "influx", "gene influx",
        "bottleneck", "genetic bottleneck", "founder", "founding",
        "founding population", "founder lineage", "founder effect",
        "endogamy", "endogamous", "inbreeding", "absorbed", "interbred",
        "interbreed", "admixture event", "secondary admixture", "allele sharing",
        "consanguineous", "consanguinity", "intermarry", "intermarrying",
    ],
    "archaic_and_deep_lineage": [
        "denisovan", "denisovans", "neanderthal", "neanderthals", "hominin",
        "hominins", "archaic", "archaic admixture", "archaic human",
        "deeply branching", "deep split", "deep lineage", "divergent lineage",
        "oldest living population", "oldest population", "ancient ancestral",
        "ancestral south indians", "aasi", "xooa", "extant humans",
        "anatomically modern humans", "modern human", "most divergent",
    ],
    "social_structure": [
        "caste", "caste system", "endogamy", "endogamous", "exogamy",
        "stratified", "stratification", "occupational", "occupational segregation",
        "marginalized", "marginalised", "taboo", "tribe", "tribal", "clan",
        "kinship", "lineage system", "social division", "hierarchy",
        "hierarchical", "consanguineous", "intermarriage",
    ],
    "migration_conquest": [
        "conquest", "conquerors", "conquered", "invasion", "invaders",
        "nomadic", "nomad", "expelled", "deported", "deportation", "refugee",
        "refugees", "exile", "displacement", "displaced", "fled", "fleeing",
        "raid", "raids", "incursion", "settlement wave", "migratory wave",
    ],
    "race_classification": [
        "race", "racial", "racially", "racialized", "racialised",
        "racial classification", "racial category", "racial type",
        "caucasian", "caucasoid", "mongoloid", "negroid", "australoid",
        "capoid", "proto-caucasian", "sub-race", "subrace",
        "anthropological", "anthropologist", "anthropometric", "anthropometry",
        "physical anthropology", "craniometric", "craniometry", "cranial",
        "typology", "typological", "phenotypically", "race science",
        "phrenology",
    ],
}


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------

def load_paragraphs(
    input_path: str,
) -> tuple[list[str], list[str], list[str], list[bool]]:
    """
    Load per-paragraph corpus units from a directory or manifest file.

    Each input file is treated as one DOCUMENT containing multiple paragraphs
    separated by newlines. Every non-empty paragraph becomes its own corpus
    unit. Category: lines are stripped first, and blank lines are skipped so
    that runs of newlines do not produce empty paragraphs.

    Returns four parallel lists:
        ids       — per-paragraph identifier, e.g. "doc.txt#p3"
        documents — the source document path for each paragraph
        texts     — the paragraph text
        skipped   — one boolean PER ORIGINAL INPUT LINE, across all documents
                    in the order they were read: True if that line was skipped
                    (blank line or Category: line), False if it became a
                    paragraph. Lets callers realign results with the raw input.
    """
    p = Path(input_path)

    if p.is_dir():
        paths = sorted(p.glob("*.txt"))
    elif p.is_file():
        lines = p.read_text(encoding="utf-8").splitlines()
        paths = [Path(line.strip()) for line in lines if line.strip()]
    else:
        print(f"Error: {input_path} is not a directory or file")
        sys.exit(1)

    if not paths:
        print(f"Error: no input documents found at {input_path}")
        sys.exit(1)

    ids: list[str] = []
    documents: list[str] = []
    texts: list[str] = []
    skipped: list[bool] = []

    for fp in paths:
        try:
            raw = fp.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  Warning: could not read {fp} ({e})")
            continue

        # Walk every original line in order so the skipped mask stays aligned
        # with the raw input. A line is skipped if it is a Category: line or
        # is blank after stripping; otherwise it becomes a paragraph.

        # Note: There was an issue here with discussion IDs being generated in a different script
        # If the "continue" is commented out, it's because of that
        para_index = 0
        for line in raw.splitlines():
            #if line.startswith("Category:") or not line.strip():
            #    skipped.append(True)
                #continue
            para_index += 1
            ids.append(f"{fp.name}#p{para_index}")
            documents.append(str(fp))
            texts.append(line.strip())
            skipped.append(False)

    if not texts:
        print("Error: no non-empty paragraphs to analyze")
        sys.exit(1)

    return ids, documents, texts, skipped


def load_categories(path: str | None) -> dict[str, list[str]]:
    """Load category definitions from JSON, or return the built-in defaults."""
    if path is None:
        return DEFAULT_CATEGORIES
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("Error: categories JSON must be an object of {category: [terms]}")
        sys.exit(1)
    return data


# ---------------------------------------------------------------------------
# Term matching
# ---------------------------------------------------------------------------

# Known false-positive contexts. Any text matching one of these patterns is
# removed BEFORE term counting, so the phrase cannot trigger a category hit.
# This is for cases where a category term (e.g. "dna") legitimately appears as
# a substring of an unrelated proper noun — here, the news outlets "DNA India"
# and "dnaindia" / "dnaindia.com", which are not about genetics.
#
# Add a compiled, case-insensitive pattern here for any new false positive you
# need to suppress. Patterns are applied in order; each match is replaced with
# a single space so it cannot be counted and cannot merge adjacent words.
EXCLUSION_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bdna\s+india\b", re.IGNORECASE),
    re.compile(r"\bdnaindia(?:\.com)?\b", re.IGNORECASE),
]


def apply_exclusions(text: str) -> str:
    """Blank out known false-positive phrases before term counting."""
    for pattern in EXCLUSION_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def compile_patterns(
    categories: dict[str, list[str]],
) -> dict[str, dict[str, re.Pattern]]:
    """
    Pre-compile a word-boundary regex for every term in every category.

    Using \\b boundaries ensures "cluster" matches as a whole word and not
    inside "blockbuster". Multi-word phrases are matched with flexible
    whitespace so "allele   frequency" still matches "allele frequency".
    Matching is case-insensitive.
    """
    compiled: dict[str, dict[str, re.Pattern]] = {}
    for category, terms in categories.items():
        compiled[category] = {}
        for term in terms:
            # Escape regex metacharacters, then allow flexible internal whitespace
            escaped = r"\s+".join(re.escape(part) for part in term.split())
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            compiled[category][term] = pattern
    return compiled


def count_terms_in_text(
    text: str,
    compiled: dict[str, dict[str, re.Pattern]],
) -> dict[str, Counter]:
    """
    Count occurrences of every category term in a single text.

    Known false-positive phrases (see EXCLUSION_PATTERNS) are removed first,
    so e.g. the "DNA India" news source does not count as a "dna" hit.

    Returns {category: Counter({term: count})}, including only terms that
    actually appeared at least once.
    """
    text = apply_exclusions(text)
    result: dict[str, Counter] = {}
    for category, term_patterns in compiled.items():
        hits = Counter()
        for term, pattern in term_patterns.items():
            n = len(pattern.findall(text))
            if n:
                hits[term] = n
        if hits:
            result[category] = hits
    return result


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(
    ids: list[str],
    documents: list[str],
    texts: list[str],
    categories: dict[str, list[str]],
    min_count: int = 1,
) -> tuple[list[dict], dict]:
    """
    Run terminology categorization across the whole corpus.

    Returns:
      per_paragraph — list of dicts, one per paragraph, each with:
          id, document, total_terms, and {category: count} for matched
          categories (categories whose total hits in the paragraph >= min_count)
      corpus_stats — aggregate dict with corpus-level and per-document stats
    """
    compiled = compile_patterns(categories)

    per_paragraph: list[dict] = []
    category_paragraph_counts: Counter = Counter()
    category_term_totals: Counter = Counter()
    term_frequencies: dict[str, Counter] = defaultdict(Counter)

    # Per-document aggregation: how many paragraphs in each document hit
    # each category, so framing can be summarized at the document level too.
    doc_category_counts: dict[str, Counter] = defaultdict(Counter)
    doc_paragraph_totals: Counter = Counter()

    for ident, document, text in zip(ids, documents, texts):
        matched = count_terms_in_text(text, compiled)
        doc_paragraph_totals[document] += 1

        row: dict = {"id": ident, "document": document, "total_terms": 0}
        for category, hits in matched.items():
            cat_total = sum(hits.values())
            if cat_total < min_count:
                continue
            row[category] = cat_total
            row["total_terms"] += cat_total

            # Aggregate corpus-level stats
            category_paragraph_counts[category] += 1
            category_term_totals[category] += cat_total
            for term, n in hits.items():
                term_frequencies[category][term] += n

            # Aggregate per-document stats
            doc_category_counts[document][category] += 1

        per_paragraph.append(row)

    corpus_stats = {
        "n_paragraphs": len(ids),
        "n_documents": len(set(documents)),
        "category_paragraph_counts": category_paragraph_counts,
        "category_term_totals": category_term_totals,
        "term_frequencies": term_frequencies,
        "doc_category_counts": doc_category_counts,
        "doc_paragraph_totals": doc_paragraph_totals,
    }
    return per_paragraph, corpus_stats


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def write_skipped_mask(path: str, skipped: list[bool]) -> None:
    """
    Write one boolean per ORIGINAL input line, in order, one per output line.

    "True" means the line was skipped (blank or Category: line) and did not
    become a paragraph; "False" means it became a paragraph and appears in the
    results. The number of lines here equals the number of lines in the input,
    so callers can realign per-paragraph output with their raw input data.
    """
    # Create the parent directory if the user gave a nested path
    parent = Path(path).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for flag in skipped:
            f.write("True\n" if flag else "False\n")
    n_skipped = sum(skipped)
    print(f"  Skipped mask written to: {path} "
          f"({len(skipped)} lines, {n_skipped} skipped)")


def write_csv(
    csv_path: str,
    per_paragraph: list[dict],
    categories: dict[str, list[str]],
) -> None:
    """
    Write per-paragraph category counts to CSV.

    One row per paragraph; one column per category plus id and total.
    A zero means the category had no matching terms in that paragraph.
    """
    category_names = list(categories.keys())
    fieldnames = ["id", "document", "total_terms"] + category_names

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in per_paragraph:
            full_row = {name: row.get(name, 0) for name in fieldnames}
            writer.writerow(full_row)

    print(f"  Per-paragraph CSV written to: {csv_path}")


def write_summary(
    summary_path: str,
    corpus_stats: dict,
    categories: dict[str, list[str]],
    top_terms: int = 15,
) -> None:
    """
    Write a corpus-level summary report.

    For each category: how many paragraphs contained it, total term hits,
    and the most frequent individual terms within that category.
    """
    n = corpus_stats["n_paragraphs"]
    n_docs = corpus_stats.get("n_documents", 0)
    para_counts = corpus_stats["category_paragraph_counts"]
    term_totals = corpus_stats["category_term_totals"]
    term_freqs = corpus_stats["term_frequencies"]

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append(" Seeded Terminology Categorization — Summary")
    lines.append("=" * 60)
    lines.append(f" Documents analyzed : {n_docs}")
    lines.append(f" Paragraphs analyzed: {n}")
    lines.append("")
    lines.append(" Note: counts describe how the text is written —")
    lines.append(" which terminology appears — not properties of the")
    lines.append(" populations the text discusses.")
    lines.append("")

    # Order categories by how many paragraphs they appear in
    ordered = sorted(
        categories.keys(),
        key=lambda c: para_counts.get(c, 0),
        reverse=True,
    )

    for category in ordered:
        p_count = para_counts.get(category, 0)
        t_total = term_totals.get(category, 0)
        pct = (p_count / n * 100) if n else 0.0

        lines.append("-" * 60)
        lines.append(f" {category}")
        lines.append(f"   Paragraphs containing it : {p_count}  ({pct:.1f}%)")
        lines.append(f"   Total term occurrences   : {t_total}")

        freqs = term_freqs.get(category, Counter())
        if freqs:
            lines.append(f"   Most frequent terms:")
            for term, count in freqs.most_common(top_terms):
                lines.append(f"     {count:>5}  {term}")
        lines.append("")

    lines.append("=" * 60)

    report = "\n".join(lines)
    Path(summary_path).write_text(report, encoding="utf-8")
    print(f"  Summary report written to: {summary_path}")
    # Also echo to console
    print()
    print(report)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    print(f"\nLoading corpus from: {args.input}")
    ids, documents, texts, skipped = load_paragraphs(args.input)
    n_docs = len(set(documents))
    print(f"  Loaded {len(texts)} paragraphs from {n_docs} documents")

    if args.skipped_mask:
        write_skipped_mask(args.skipped_mask, skipped)

    categories = load_categories(args.categories)
    print(f"  Using {len(categories)} terminology categories")

    print("\nScanning for category terms...")
    per_paragraph, corpus_stats = analyze(
        ids, documents, texts, categories, min_count=args.min_count
    )

    write_csv(args.csv, per_paragraph, categories)
    write_summary(args.summary, corpus_stats, categories)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seeded terminology categorization for a paragraph corpus."
    )
    parser.add_argument(
        "input",
        help="Directory of .txt files, or a manifest file listing paths",
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        default="term_counts.csv",
        help="Per-paragraph category counts CSV (default: term_counts.csv)",
    )
    parser.add_argument(
        "--summary",
        metavar="PATH",
        default="term_summary.txt",
        help="Corpus-level summary report (default: term_summary.txt)",
    )
    parser.add_argument(
        "--categories",
        metavar="PATH",
        default=None,
        help="JSON file overriding default category definitions",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        metavar="N",
        help="Min term hits in a paragraph to assign a category (default: 1)",
    )
    parser.add_argument(
        "--skipped_mask",
        nargs="?",
        const="skipped_lines.txt",
        default=None,
        metavar="PATH",
        help="Write a skipped mask: one boolean per input line (True if the "
             "line was skipped as blank/Category:, False if it became a "
             "paragraph), for realigning results with the raw input. Give a "
             "path to choose the output file, or pass the flag alone to use "
             "skipped_lines.txt. Omit entirely to write nothing.",
    )
    args = parser.parse_args()
    run(args)