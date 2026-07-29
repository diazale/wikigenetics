"""
This code extracts keywords based on a combination of regex and python string functions.

It's probably inefficient but only really needs to be run once, assuming you have your keywords figured out.

Authorship:
- Alex Diaz-Papkovich
"""

from collections import defaultdict
from dateutil.parser import parse

import argparse
import gzip
import json
import requests
import time

import os
import re

# Import custom functions
from helper_functions import *

parser = argparse.ArgumentParser("Extract keywords from articles and summarize the contents.")

parser.add_argument("--contents_dir", metavar="Directory of revision texts", type=str, dest="contents_dir",
                    help="Where downloaded revision data are stored.",
                    default="/users/adiazpap/data/datasets/wikipedia/data/revision_contents_processed")
parser.add_argument("--revisions_dir", metavar="Directory of revision histories", type=str,
                    dest="revisions_dir",
                    help="Where downloaded revision histories are stored.",
                    default="/users/adiazpap/data/datasets/wikipedia/data/revision_histories")
parser.add_argument("--kw_results_dir", metavar="Directory to store keyword results", type=str,
                    dest="kw_results_dir",
                    help="Where to store results from this script.",
                    default="/users/adiazpap/data/datasets/wikipedia/data/keyword_results")
parser.add_argument("--keywords_file", metavar="File containing list of keywords", type=str,
                    dest="keywords_file",
                    help="File with each line containing a keyword.",
                    default="/users/adiazpap/wikistudy/metadata/genetics_terms.txt")
parser.add_argument("--caps_terms_file", metavar="File containing list of all-caps terms", type=str,
                    dest="caps_terms_file",
                    help="File with each lining containing a keyword that must be in all-caps.",
                    default="/users/adiazpap/wikistudy/metadata/caps_terms.txt")
parser.add_argument("--start_date", metavar="Earliest revision date to use", type=str,
                    dest="start_date", default="2001-01-01",
                    help="Earliest revision date to consider, written YYYY-MM-DD.")
parser.add_argument("--pages_file", metavar="File of pages to parse", type=str,
                    dest="pages_file", 
                    help="File with each line containing a page to parse, in .txt.gz format.",
                    default="/users/adiazpap/wikistudy/metadata/test_pages_list.txt")

args = parser.parse_args()

contents_dir = args.contents_dir
revisions_dir = args.revisions_dir
kw_results_dir = args.kw_results_dir
keywords_file = args.keywords_file
caps_terms_file = args.caps_terms_file
pages_file = args.pages_file
start_date = args.start_date

with open(args.keywords_file) as f:
    genetics_terms = f.read().strip().split("\n")
f.close()

with open(args.caps_terms_file) as f:
    caps_terms = f.read().strip().split("\n")
f.close()

with open(args.pages_file) as f:
    pages = f.read().strip().split("\n")
f.close()

start = time.time()

search_string_list = genetics_terms + caps_terms


pattern_dict = {}

pattern_dict["genes"] = r'\bgenes?\b'

print(pages_file)

for page_file in pages:
    if page_file.endswith(".txt.gz") and page_file[0]:
        page_title = page_file.split(".txt.gz")[0]
    
        print(page_title)
    
        try:
            revisions = parse_revision_history(os.path.join(revisions_dir, page_title + ".txt"))
            contents_path = os.path.join(contents_dir, page_title + ".txt.gz")
            
            f = gzip.open(contents_path, "rb")
            page_contents = f.read()
            f.close()
            
            # Stored by revision IDs in JSON
            # Basically call it as a dict in Python
            # Note that ' and \n are in the text and need to be replaced if viewing in an editor
            page_contents = json.loads(page_contents)
            
            counter = 0
            mentioned_revisions = list()
            earliest_mention = "2030-01-01" # use an arbitrary future data
            latest_mention = "1970-01-01" # just some default
            
            #print(search_string_list)
            
            # Main JSON object
            # Stores:
            # Page name
            # keywords
            # if the keywords were ever used
            # first_mention
            # last mention
            # list of revision JSON objects
            
            full_item = {}
            regex_results = {}
            
            ever_mentioned = False
            
            full_item["page"] = page_title
            full_item["keywords"] = search_string_list + [k for k in pattern_dict.keys()] #["genes"] # REGEX MANUALLY ADD KEYWORD
            full_item["keywords_ever_mentioned"] = ever_mentioned
            full_item["keywords_earliest_mention"] = earliest_mention
            full_item["keywords_earliest_revision"] = ""
            full_item["keywords_latest_mention"] = latest_mention
            full_item["keywords_latest_revision"] = ""
            full_item["earliest_revision"] = ""
            full_item["latest_revision"] = ""
            full_item["revisions"] = []
            
            for revision in revisions:
                ref_name = False
                if parse(revision["timestamp"]).date() > parse(start_date).date():# and counter < 10:
                    # Only look at revisions after the specified start date
    
                    if counter==0:
                        # Get the ID of the first revision
                        earliest_revision = revision["revid"]
                    
                    current_revision = page_contents[str(revision["revid"])]

                    # Replace terms that frequently cause false positives
                    current_revision = current_revision.replace("dnaindia","").replace("genetic mod","").replace("genetically mod","").replace("genetic eng","").replace("genetically eng","")

                    # regex search for "gene" and "genes" (case-insensitive)
                    #gene_results = re.findall(gene_pattern, current_revision, re.IGNORECASE)

                    # Carry out regex searchs
                    for k in pattern_dict.keys():
                        regex_results[k] = re.findall(pattern_dict[k], current_revision, re.IGNORECASE)

                    #sum([len(regex_results[k]) for k in regex_results.keys()])

                    # Search for terms
                    if not any(search_string.lower() in current_revision.lower() for search_string in set(genetics_terms)) and \
                    not any(search_string in current_revision for search_string in caps_terms) and \
                    sum([len(regex_results[k]) for k in regex_results.keys()])==0:
                    #len(gene_results)==0:

                        # First check all keywords
                        # For genetics terms, use lowercase search; for all caps terms like DNA and PCA use case-sensitive
                        # First case: none are found
                        # If none are found, just record 0 for everything
                        temp = {}
                        temp["revid"] = revision["revid"]
                        temp["timestamp"] = revision["timestamp"]
                        temp["keywords"] = [{s: 0} for s in search_string_list] # Each keyword comes up zero times here

                        # regex terms
                        #temp["keywords"].append({"genes":0}) # REGEX COUNTING HACK
                        for k in pattern_dict.keys():
                            temp["keywords"].append({k:0})
                        
                        try:
                            temp["categories"] = get_page_categories(current_revision)
                        except:
                            # Sometimes categories are written incorrectly (e.g. "[[Category:cats]")
                            print("Exception trying to get categories in revision", revision["revid"])
                    
                    else:
                        # Next case: Keywords are detected
                        ever_mentioned = True # Trigger boolean for entire article history
                        # Store the results in a dict (to be converted to JSON)
                        temp = {}
                        temp["revid"] = revision["revid"]
                        temp["timestamp"] = revision["timestamp"]
                        temp["keywords"] = [] # Leave empty and populate later
                        try:
                            temp["categories"] = get_page_categories(current_revision)
                        except:
                            # Sometimes categories are written incorrectly (e.g. "[[Category:cats]")
                            print("Exception trying to get categories in revision", revision["revid"])
    
                        # For mentions of any keyword
                        for search_string in search_string_list:
                            # Identify the first and last appearance of any search terms
                            #if parse(revision["timestamp"]).date() > parse(latest_mention).date():
                            if parse(revision["timestamp"]).timestamp() > parse(latest_mention).timestamp():
                                latest_mention = revision["timestamp"]
                                full_item["keywords_latest_revision"] = revision["revid"]
                                
                            #if parse(revision["timestamp"]).date() < parse(earliest_mention).date():
                            if parse(revision["timestamp"]).timestamp() < parse(earliest_mention).timestamp():
                                earliest_mention = revision["timestamp"]
                                full_item["keywords_earliest_revision"] = revision["revid"]

                            # Count how often terms appear
                            if search_string in caps_terms:
                                # For capitalized terms we want to match case
                                temp["keywords"].append({search_string:current_revision.count(search_string)})
                            else:
                                temp["keywords"].append({search_string:current_revision.lower().count(search_string.lower())})

                        for k in pattern_dict.keys():
                            temp["keywords"].append({k:len(regex_results[k])})
                        #temp["keywords"].append({"genes":len(gene_results)}) # REGEX ADD COUNTS
            
                    full_item["revisions"].append(temp)
                    counter+=1
            
            full_item["keywords_ever_mentioned"] = ever_mentioned
            full_item["keywords_earliest_mention"] = earliest_mention
            full_item["keywords_latest_mention"] = latest_mention
            full_item["earliest_revision"] = earliest_revision
            full_item["latest_revision"] = revision["revid"]
            
            f = open(os.path.join(kw_results_dir, page_title + ".json"), "w")
            f.write(json.dumps(full_item))
            f.write("\n")
            f.close()
        except Exception as e:
            print("Exception! Article may not exist:", page_title)
            print(e)

end = time.time()

print("Time elapsed:", str(end-start))
