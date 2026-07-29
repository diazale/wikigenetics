"""
This is modified code from the manuscript analysis notebook that calculates the
length and proportion of section types. It is meant specifically to complement
the notebook used in the manuscript, but the underlying logic is pretty basic.
Some stuff is hardcoded because it is specific to the manuscript.

Given a collection of Wikipedia pages, it identifies types of sections based on
a regex input. Then it parses the historical revisions and calculates the lengths
of that type of section relative to the page and outputs a pickle file to analyze.
It is also parallelized to run (strongly recommended if you have more than a few
hundred pages).

Example usage (identifying "culture" or "society" sections) in a bash script

PAT='(?i:cultur)|(?i:societ)' # regex strings
OUT='culture_sections' # output file name

# data-dir stores parquet data for revision histories and sections
# metadata-dir is where your list of demonyms lives (if you need that)
# contents-dir-pro stores revision contents


python -u section_identifier.py \
--out-path ..."$OUT".pkl \
--data-dir data/datasets/wikipedia/data/parquet_data \
--metadata-dir metadata \
--cutoff-date 2026-01-01 \
--contents-dir-pro /users/adiazpap/data/datasets/wikipedia/data/databases/parquet/revision_contents_processed \
--pat "$PAT"

Authorship
- Mostly Alex Diaz-Papkovich
- Some optimizations with Claude Opus 4.8
"""

# =============================================================================
# Standard library
# =============================================================================
import argparse
import datetime
import itertools
import os
import pickle
import re
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

# =============================================================================
# Third-party
# =============================================================================
import numpy as np
import pandas as pd
import wikitextparser as wtp

# =============================================================================
# Argument parsing
# =============================================================================
def parse_args():
    parser = argparse.ArgumentParser(description="Identify section types based on title and calculate their lengths and proportions.")

    parser.add_argument("--data-dir",         required=True,  help="Directory storing revision history and section data")
    parser.add_argument("--metadata-dir",     required=True,  help="Base metadata directory")
    parser.add_argument("--cutoff-date",      required=True,  help="Cutoff date in YYYY-MM-DD format")
    parser.add_argument("--out-path",         default="~/scratch/section_counts.pkl", help="Full path to output pickle file")
    parser.add_argument("--contents-dir-pro", required=True,  help="Directory containing each page's processed revision data")
    parser.add_argument("--n-workers",        type=int, default=None, help="Number of parallel workers (defaults to SLURM_CPUS_PER_TASK, then 4)")
    parser.add_argument("--pat",              default=r'DNA|(?i:genet)|(?i:admix)|(?i:biobank)|(?i:genom)|(?i:chromosom)|(?i:autosom)|(?i:genotyp)|(?i:mitochon)|(?i:haplo)',
                                              help="Regex pattern for identifying sections. Defaults to genetic sections.")
    parser.add_argument("--genetics",         action="store_true",  help="Limit analysis to pages that have genetics sections")

    return parser.parse_args()


args = parse_args()

# =============================================================================
# User-defined configuration
# =============================================================================
data_dir         = args.data_dir
metadata_dir     = args.metadata_dir
cutoff_date      = datetime.date.fromisoformat(args.cutoff_date)
out_path         = os.path.expanduser(args.out_path)
contents_dir_pro = args.contents_dir_pro
n_workers        = args.n_workers or int(os.environ.get("SLURM_CPUS_PER_TASK", 4))
genetics         = args.genetics

# =============================================================================
# Detect section patterns
# =============================================================================
pat_section          = args.pat
pat_section_compiled = re.compile(pat_section)
pat_genetics         = r'DNA|(?i:genet)|(?i:admix)|(?i:biobank)|(?i:genom)|(?i:chromosom)|(?i:autosom)|(?i:genotyp)|(?i:mitochon)|(?i:haplo)'
pat_genetics_compiled = re.compile(pat_genetics)

# =============================================================================
# Helpers
# =============================================================================
def dict_int(data_dict, *keys):
    """Return the intersection of sets stored in data_dict at the given keys."""
    if not keys:
        return set()
    return set.intersection(*(data_dict[k] for k in keys))


# =============================================================================
# Worker function
# =============================================================================
def process_page(page_title, temp_set):
    # Identify relevant sections based on regex patterns
    # Lengths are character counts
    page_contents = pd.read_parquet(os.path.join(contents_dir_pro, page_title + ".parquet"))
    page_contents_indexed = page_contents.set_index("revision_id")["markup"]
    del page_contents

    rev_ids = [r for r in page_contents_indexed.index if r in temp_set]

    t0      = time.time()
    counter = 0

    # All dicts have rev_id as keys
    local_overall_summary       = {} # Boolean indicator if the page has any relevant sections
    local_page_summary          = {} # Container variable
    local_overall_levels        = {} # Levels of every section
    local_overall_titles        = {} # Titles of every section
    local_overall_lengths       = {} # Lengths of every section
    local_overall_words         = {} # Words in every section
    local_overall_booleans      = {} # Boolean indicators if a section has keyword
    local_overall_page_lengths  = {} # Total page length
    local_overall_page_words    = {} # Total number of words
    local_overall_intro_lengths = {} # Length of intro

    for rev_id in rev_ids:
        counter += 1
        if counter % 25 == 0 or counter == len(rev_ids):
            print(f"  [{page_title}] Revision {counter} of {len(rev_ids)}", flush=True)

        rev             = "\n".join(page_contents_indexed.loc[rev_id].splitlines())
        parsed          = wtp.parse(rev)
        sections_parsed = parsed.sections

        # Edge case: No sections (not interested in this here)
        if len(sections_parsed) == 1:
            continue

        # Convert parsed data to plaintext
        parsed_plain_text     = re.sub(r'\s+', ' ', parsed.plain_text())
        parsed_plain_text_len = len(parsed_plain_text)
        section_plain_texts   = [re.sub(r'\s+', ' ', s.plain_text()) for s in sections_parsed]

        # Extract information from sections and identify relevant sections
        section_levels   = [s.level for s in sections_parsed]
        section_titles   = [s.title for s in sections_parsed]
        section_lengths  = [len(t) for t in section_plain_texts]
        section_words    = [len(t.split()) for t in section_plain_texts]
        section_boolean  = [
            bool(pat_section_compiled.search(t)) if t is not None else False
            for t in section_titles
        ]

        # Store local results for the revision
        local_overall_levels[rev_id]        = section_levels
        local_overall_titles[rev_id]        = section_titles
        local_overall_lengths[rev_id]       = section_lengths
        local_overall_words[rev_id]         = section_words
        local_overall_booleans[rev_id]      = section_boolean
        local_overall_page_lengths[rev_id]  = parsed_plain_text_len
        local_overall_page_words[rev_id]    = len(parsed_plain_text.split())
        local_overall_intro_lengths[rev_id] = len(section_plain_texts[0])

        # Identify the highest level of section and get the indices of relevant sections
        highest_level      = min(section_levels[1:])
        section_levels_arr = np.array(section_levels)

        indicator_indices = [
            s for s, title in enumerate(section_titles)
            if title is not None and pat_section_compiled.search(title)
        ]

        # Skip the loop if there are no relevant sections
        if not indicator_indices:
            continue

        local_overall_summary[rev_id] = True
        local_page_summary[rev_id] = {
            "section_title":        [],
            "section_type":         [],
            "section_position_abs": [],
            "section_position_rel": [],
            "section_length":       [],
            "section_proportion":   [],
            "section_level":        [],
        }

        # For relevant sections, record the information
        for s in indicator_indices:
            level_s      = section_levels[s]
            section_type = (level_s - highest_level) * "sub" + "section"

            if level_s == highest_level:
                relative_section_position = int(
                    np.sum(section_levels_arr[:s] == highest_level) + 1
                )
            else:
                relative_section_position = sum(
                    1 for _ in itertools.takewhile(
                        lambda a: a, (section_levels_arr[:s+1] == level_s)[::-1]
                    )
                )

            section_length     = section_lengths[s]
            section_proportion = round(section_length / parsed_plain_text_len, 5)

            local_page_summary[rev_id]["section_title"].append(section_titles[s])
            local_page_summary[rev_id]["section_type"].append(section_type)
            local_page_summary[rev_id]["section_position_abs"].append(s)
            local_page_summary[rev_id]["section_position_rel"].append(relative_section_position)
            local_page_summary[rev_id]["section_length"].append(section_length)
            local_page_summary[rev_id]["section_proportion"].append(section_proportion)
            local_page_summary[rev_id]["section_level"].append(level_s)

    print(f"  [{page_title}] Loop time: {time.time() - t0:.2f}s", flush=True)

    return (
        local_overall_summary,
        local_page_summary,
        local_overall_levels,
        local_overall_titles,
        local_overall_lengths,
        local_overall_words,
        local_overall_booleans,
        local_overall_page_lengths,
        local_overall_page_words,
        local_overall_intro_lengths,
    )


# =============================================================================
# Load data
# =============================================================================
revision_histories = pd.read_parquet(
    os.path.join(data_dir, "databases/parquet/revision_histories.parquet"),
    columns=["page_name", "revision_id", "parent_id", "minor", "user",
             "user_id", "size", "comment", "tags", "timestamp"]
).rename(columns={"timestamp": "datetime"})

sections = pd.read_parquet(
    os.path.join(data_dir, "databases/parquet/sections.parquet"),
    columns=["revision_id", "section_title", "section_rank",
             "section_level", "keyword_ever_mentioned"]
)

demonym_df = pd.read_csv(os.path.join(metadata_dir, "demonyms6.csv"))

with open(os.path.join(metadata_dir, "filtering_lists/allow_list_20260224.txt")) as f:
    in_scope_articles = f.read().strip().split("\n")

# =============================================================================
# Scope filtering
# =============================================================================
EXCLUDED_DEMOGRAPHICS = {
    "Demographics_of_Abkhazia",
    "Demographics_of_Northern_Cyprus",
    "Demographics_of_Western_Sahara",
    "Demographics_of_Ireland",
}

scope_articles     = []
scope_demographics = []

for s in in_scope_articles:
    if "Demographic" not in s:
        scope_articles.append(s)
    elif s not in EXCLUDED_DEMOGRAPHICS:
        scope_demographics.append(s)

scope_articles_set     = set(scope_articles)
scope_demographics_set = set(scope_demographics)

# =============================================================================
# Revision ID sets
# =============================================================================
revision_ids = {}

revision_ids["cutoff"] = set(
    revision_histories[revision_histories["datetime"].dt.date < cutoff_date]["revision_id"]
)
revision_ids["in_scope"] = set(
    revision_histories[revision_histories["page_name"].isin(in_scope_articles)]["revision_id"]
)
revision_ids["genetics_of"] = set(
    revision_histories[
        revision_histories["page_name"].str.startswith("Genetic") |
        revision_histories["page_name"].str.startswith("Y-DNA")
    ]["revision_id"]
)
revision_ids["demographics"] = set(
    revision_histories[revision_histories["page_name"].isin(scope_demographics_set)]["revision_id"]
)
revision_ids["last"] = set(
    revision_histories[revision_histories["datetime"].dt.date < cutoff_date]
    .sort_values(["page_name", "datetime"], ascending=[True, True])
    .groupby("page_name").last()["revision_id"]
)

_temp = revision_histories[["page_name", "revision_id", "datetime"]].copy()
_temp["day"] = _temp["datetime"].dt.to_period("D")
_last_day = (
    _temp.sort_values("datetime")
    .groupby(["page_name", "day"], as_index=False)
    .last()[["page_name", "day", "revision_id", "datetime"]]
)
revision_ids["last_day"] = set(_last_day["revision_id"])

revision_ids["has_section"] = set(
    sections[sections["section_title"].str.contains(pat_section, na=False)]["revision_id"]
)

revision_ids["genetics_section"] = set(
    sections[sections["section_title"].str.contains(pat_genetics, na=False)]["revision_id"]
)

revision_ids["corpus"] = (
    (revision_ids["in_scope"] & revision_ids["cutoff"])
    - revision_ids["genetics_of"]
    - revision_ids["demographics"]
)

# =============================================================================
# Identify target revisions and pages
# =============================================================================
if genetics:
    # If we want to limit analysis to pages with genetics sections
    temp_revids = dict_int(revision_ids, "corpus", "last", "has_section", "genetics_section")
else:
    temp_revids = dict_int(revision_ids, "corpus", "last", "has_section")

temp_page_names = list(
    revision_histories[revision_histories["revision_id"].isin(temp_revids)]["page_name"].unique()
)
temp_set = dict_int(revision_ids, "cutoff", "last_day")

del revision_histories
del sections
del revision_ids

# =============================================================================
# Output containers
# =============================================================================
overall_summary       = {}
page_summary          = {}
overall_levels        = {}
overall_titles        = {}
overall_lengths       = {}
overall_words         = {}
overall_booleans      = {}
overall_page_lengths  = {}
overall_page_words    = {}
overall_intro_lengths = {}

# =============================================================================
# Parallelized main loop
# =============================================================================
with ProcessPoolExecutor(max_workers=n_workers) as executor:
    futures = {executor.submit(process_page, page_title, temp_set): page_title
               for page_title in temp_page_names}

    for future in as_completed(futures):
        page_title = futures[future]
        try:
            (
                local_overall_summary,
                local_page_summary,
                local_overall_levels,
                local_overall_titles,
                local_overall_lengths,
                local_overall_words,
                local_overall_booleans,
                local_overall_page_lengths,
                local_overall_page_words,
                local_overall_intro_lengths,
            ) = future.result()

            overall_summary.update(local_overall_summary)
            page_summary.update(local_page_summary)
            overall_levels.update(local_overall_levels)
            overall_titles.update(local_overall_titles)
            overall_lengths.update(local_overall_lengths)
            overall_words.update(local_overall_words)
            overall_booleans.update(local_overall_booleans)
            overall_page_lengths.update(local_overall_page_lengths)
            overall_page_words.update(local_overall_page_words)
            overall_intro_lengths.update(local_overall_intro_lengths)

            print(f"Completed: {page_title}", flush=True)
        except Exception as e:
            print(f"Error processing {page_title}: {e}", flush=True)

# =============================================================================
# Save output
# =============================================================================
output = {
    "page_summary":          page_summary,
    "overall_summary":       overall_summary,
    "overall_levels":        overall_levels,
    "overall_titles":        overall_titles,
    "overall_lengths":       overall_lengths,
    "overall_words":         overall_words,
    "overall_booleans":      overall_booleans,
    "overall_page_lengths":  overall_page_lengths,
    "overall_page_words":    overall_page_words,
    "overall_intro_lengths": overall_intro_lengths,
}

with open(out_path, "wb") as f:
    pickle.dump(output, f, protocol=pickle.HIGHEST_PROTOCOL)
