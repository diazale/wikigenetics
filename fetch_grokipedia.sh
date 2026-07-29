#!/bin/bash

# Download all Grokipedia pages listed in a metadata file

# The file containing the list of page names (one per line)
INPUT_FILE="metadata/demonyms_existing_202601.txt"

# Base URL for Grokipedia (adjust if the actual URL structure differs)
BASE_URL="https://grokipedia.com/page"

# The suffix requested for the output files
DATE_SUFFIX="20260406"

# Check if the input file exists before starting
if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: File '$INPUT_FILE' not found."
    exit 1
fi

echo "Starting download of Grokipedia pages..."

# Loop through each line in the input file
while IFS= read -r page || [[ -n "$page" ]]; do
    # Skip empty lines
    [[ -z "$page" ]] && continue

    # 1. Replace spaces with underscores for the URL (common wiki format)
    # 2. Construct the full URL
    URL_NAME=$(echo "$page" | tr ' ' '_')
    FULL_URL="${BASE_URL}/${URL_NAME}"
    
    # Define the output filename
    OUTPUT_FILE="${page}_${DATE_SUFFIX}.html"

    echo "Downloading: $page -> $OUTPUT_FILE"

    # Use curl to download the page
    # -s: Silent mode (hides progress bar)
    # -L: Follow redirects (important for wikis)
    # -o: Specify output file
    curl -s -L "$FULL_URL" -o "$OUTPUT_FILE"

    # Optional: Check if the download was successful
    if [[ $? -eq 0 ]]; then
        echo "Successfully saved $OUTPUT_FILE"
    else
        echo "Failed to download $page"
    fi

done < "$INPUT_FILE"

echo "Done! All pages have been processed."
