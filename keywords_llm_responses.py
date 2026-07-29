"""
This script parses a markdown file for genetics keywords.
We used it to identify keywords in LLM responses.
Authorship:
- Alex Diaz-Papkovich, with the aid of Claude Sonnet 4.6.
"""

import argparse
import re
import os

# The dictionary of regex patterns provided
kw_patterns = {
    'DNA': re.compile(r'\bDNA\b'),
    'genes': re.compile(r'\bgenes?\b', re.IGNORECASE),
    'PCA': re.compile(r'PCA'),
    'admix': re.compile(r'admix', re.IGNORECASE),
    'autosom': re.compile(r'autosom', re.IGNORECASE),
    'chromosom': re.compile(r'chromosom', re.IGNORECASE),
    'genetic': re.compile(r'genetic', re.IGNORECASE),
    'genom': re.compile(r'genom', re.IGNORECASE),
    'genotyp': re.compile(r'genotyp', re.IGNORECASE),
    'haplo': re.compile(r'haplo', re.IGNORECASE),
    'mitochon': re.compile(r'mitochon', re.IGNORECASE),
    'mt-DNA': re.compile(r'mt-DNA', re.IGNORECASE),
    'mtDNA': re.compile(r'mtDNA', re.IGNORECASE),
    'principal component': re.compile(r'principal component', re.IGNORECASE),
    'x chromosom': re.compile(r'x chromosom', re.IGNORECASE),
    'x-chromosom': re.compile(r'x-chromosom', re.IGNORECASE),
    'y chromosom': re.compile(r'y chromosom', re.IGNORECASE),
    'y-chromosom': re.compile(r'y-chromosom', re.IGNORECASE),
    'y-DNA': re.compile(r'y-DNA', re.IGNORECASE),
    'yDNA': re.compile(r'yDNA', re.IGNORECASE)
}


def main():
    # Set up argparse
    parser = argparse.ArgumentParser(description="Scan a markdown file for genetic keywords.")

    parser.add_argument('--input_file', required=True, help="Path to the input markdown file.")
    parser.add_argument('--output_file', help="Path to the output results file.")

    args = parser.parse_args()

    # Determine output file path if not provided
    if not args.output_file:
        file_root, file_ext = os.path.splitext(args.input_file)
        output_path = f"{file_root}_keyword_results{file_ext}"
    else:
        output_path = args.output_file

    # Read the input file content
    try:
        with open(args.input_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: The file '{args.input_file}' was not found.")
        return

    # Result 2: Calculate counts for each pattern
    counts = {}
    any_found = False

    # Look at each key and pattern
    for key, pattern in kw_patterns.items():
        match_count = len(pattern.findall(content)) # Length of the list of results for the pattern
        counts[key] = match_count # Update the dict of counts for the keyword
        if match_count > 0:
            # Boolean flag if there are ANY keywords found
            any_found = True

    # Writing results to the output file
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # Result 1: ANY KEYWORDS indicator
            f.write(f"ANY KEYWORDS: {any_found}\n\n")

            # Result 2: Individual keyword counts
            for key, count in counts.items():
                f.write(f"{key}: {count}\n")

        print(f"Analysis complete. Results saved to: {output_path}")

    except Exception as e:
        print(f"An error occurred while writing to the file: {e}")


if __name__ == "__main__":
    main()