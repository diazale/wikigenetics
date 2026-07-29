# Human genetics research in the public-facing information ecosystem

This repository contains the code used to collect and analyze data for the 2026 manuscript *From Wikipedia to AI: Measuring 25 years of synthesis of human genetics research in the public-facing information ecosystem*.

## Data

Grokipedia data is available on Zenodo: 

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21537405.svg)](https://doi.org/10.5281/zenodo.21537405)

The Wikipedia revision histories and contents are also available on Zenodo, as are the longitudinal measures of section lengths:

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21649943.svg)](https://doi.org/10.5281/zenodo.21649943)

Data from either website can be retrieved via cURL (for Grokipedia) or the Wikipedia API. 
Because the content is dynamic, it will not always match the data we have provided at the repositories.

Smaller datasets, such as those used in analysis of LLM responses, are available in the `data` folder.

Clickstream data can be downloaded at https://dumps.wikimedia.org/other/clickstream/

## Code

To access the Wikipedia API you must pass a header to the `query` function location in `helper_functions.py`,
e.g. `{"User-Agent":"MyBot/0.3 (me@email.com)"}`.
Registration is not required.

The default directory structure of this project is

```
-wikigenetics/
|- data/
|  |- category_members/
|  |- revision_histories/
|  |- revision_contents_processed/
|  |- revision_contents_raw/
|  |- pageviews/
|- logs/

```

The API will return JSON data.
Each line of revision history data is its own JSON object, e.g.

`{"revid": 1079717274, "parentid": 964688689, "minor": false, "user": "Ffffrr", "userid": 41865877, "timestamp": "2022-03-28T07:35:20Z", "size": 763, "slots": {"main": {"size": 763}}, "comment": "Importing Wikidata [[Wikipedia:Short description|short description]]: \"Inhibitory SMAD proteins\" ([[Wikipedia:Shortdesc helper|Shortdesc helper]])", "tags": []}`

Processed markup data is returned as a single JSON object with revision ID and markup as the key:value pair, e.g.

`"1079717274": "{{Short description|Inhibitory SMAD proteins}}\n'''I-SMAD or Inhibitor SMAD''' is a subclass..."`

### Wikipedia data
* `helper_functions.py`: A collection of functions common to retrieving and processing Wikipedia data.
* `get_category_members.py`: Gets the members of a Wikipedia category. This may contain non-article content (e.g user pages, templates, meta pages, etc.).
* `get_revision_history.py`: Gets the revision history for a given Wikipedia page
* `get_article_contents.py`: Gets the contents of every revision for a page, given the output from `get_revision_history.py`. Page markup is retrieved in chunks of 50 or fewer at a time. Very large pages may have very many files ("raw")
* `crawl_category.py`: Retrieves the members of a category as well as all of the revision histories and revision contents of every member. You can also specify depth (default 0) to retrieve data from sub-categories. ***WARNING:*** Sub-categories will sometimes contain their parent categories and can result in an endless loop if you force overwrites via `--force`.
* `get_subpages.py`: Gets subpages of a Wikipedia page. Subpages on Wikipedia exist via a forward slash (`/`) on a page and are normally used in meta pages or talk pages (e.g. `Talk:Canadians/Archive 1` is a subpage of `Talk:Canadians`). The main use case here is to retrieve talk page archives.
* `get_pageviews.py`: Gets the pageviews for a list of pages.
* `keyword_extraction_regex.py`: Identifies keywords in markup
* `section_identifier.py`: Identifies types of sections and their lengths (e.g. sections with "Genetics" in their name)
* `populate_database.py`: Converts data to a database via SQL Alchemy. Note: we eventually converted our data to parquet files for faster retrieval but kept this code.

### Grokipedia data
* `fetch_grokipedia.sh`: A shell script that uses cURL to download Grokipedia pages.
* `parse_grokipedia.py`: A script to parse Grokipedia's HTML and return text and references.

### Analysis

* `ms_analyses_cleaned.ipynb`: Most of the manuscript analyses are here. Also has the code to extract plain text paragraphs of markup with/without genetics keywords.
* `case_studies_cleaned.ipynb`: For analyzing case studies. Mostly for working with clickstream data and checking specific substrings for hereditarian writing.
* `grokipedia_analysis_cleaned.ipynb`: Analysis of Grokipedia data
* `compare_files.py`: Comparing files using TF-IDF and/or log-odds of terms.
* `analyze_seeded_terminology.Rmd`: Hierarchical clustering and analysis of topics in Wikipedia paragraphs containing genetics keywords.

### Visualizaton

* `gggplot_themes.R`: Custom ggplot2 theme based off of https://r-graph-gallery.com/web-line-chart-with-labels-at-end-of-line.html
* `keywords_plotting.Rmd`: Time series of genetics keywords
* `visualize_demonym_contexts.Rmd`: Time series and upset plot of contexts of genetics keywords in demonym pages
* `visualize_macro_trends.Rmd`: Time series of macro trends across corpus and top 1000 pages
* `visualize_wikipedia_grokipedia_differences.Rmd`: Differences between Wikipedia and Grokipedia, plus some statistical tests
* `wikipedia_sections_over_time.Rmd`: Visualizing section lengths over time. Also has some options for animated time series.
* `mapping_cleaned.ipynb`: Generate maps
