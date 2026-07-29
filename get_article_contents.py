"""
This script retrieves a page's contents based on the page title.
You must have the page's revisions available under the same name (via get_revision_history.py)

This returns the page contents in reverse chronological order as a JSON file.
The API returns data in chronological order, so we have to reverse it.

This script returns two files: 
- raw query results (there may be multiple files, which are zipped)
- processed query results (one large JSON)

The API will run into some hiccups occasionally:
- The scripts tries 50 revisions at a time
- API results have a size limit, so very long pages may have their chunks of 50 revisions split.
- Some results are suppressed (e.g. copyright violations). They will be noted in the logs.

You will probably only need to use the processed results, but if anything looks weird
you can check the raw results for comparison.

Authorship:
- Alex Diaz-Papkovich
"""

from helper_functions import *

import argparse
import glob
import os
import json
import subprocess
import sys
import time

tstamp = time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time()))

parser = argparse.ArgumentParser("Get contents of every revision of an article.")
parser.add_argument("page_title", metavar="Page title", type=str,
                    help="The page to use.")
parser.add_argument("--out_raw", metavar="out", dest="contents_dir_raw",
                    default="data/revision_contents_raw",
                    help="Output directory - raw (default data/revision_contents_raw)")
parser.add_argument("--out_pro", metavar="out", dest="contents_dir_pro",
                    default="data/revision_contents_processed",
                    help="Output directory - processed (default data/revision_contents_processed)")
parser.add_argument("--rev_dir", metavar="revs", dest="revisions_dir",
                    default="data/revision_histories",
                    help="Revision histories directory")
parser.add_argument("--log", metavar="log", dest="log_dir",
                    default="logs",
                    help="Output directory (default logs")

args = parser.parse_args()

page_title = args.page_title

contents_dir_raw = args.contents_dir_raw
contents_dir_pro = args.contents_dir_pro
revisions_dir = args.revisions_dir

log_dir = args.log_dir

if any(special in page_title for special in special_chars.keys()):
    for key, val in special_chars.items():
        page_title = page_title.replace(key, val)

page_title = page_title.replace(" ","_")

# Store our data in two folders
# One will be raw dumps of JSON, up to 50 revisions at a time, in split files
# The other will be processed data containing just the wikitext as well as the revision IDs

revisions_path = os.path.join(revisions_dir, page_title + ".txt")
log_path = os.path.join(log_dir, "log_contents_" + page_title + "_" + tstamp + ".txt") # Create timestamped log

# At the moment this doesn't do anything
# In the future, articles may have multiple slots (e.g. main content, template, infoboxes)
rvslots = "*"

# set up logging
orig_stdout = sys.stdout  # print() statements
orig_stderr = sys.stderr  # terminal statements
logf = open(log_path, 'w')
sys.stdout = logf
sys.stderr = logf

# Preamble for log
print("Article name: " + page_title)
print("Revision file: " + revisions_path)

# Import all revision IDs
revisions = parse_revision_history(revisions_path)

# The API returns results in chronological order (oldest first) so we need to reverse the list
# We do this since it only takes chunks of 50 revision IDs at a time
# This way the returned text is consistent across chunks of 50
revisions.reverse()

# Split revision IDs into lists of 50
# Separate the values by pipes for the API
n = 50 # Max number of revisions per API call

revisions_chunks = [revisions[i:i+n] for i in range(0, len(revisions), n)]

# API results are limited to a total size of 12582912
api_limit = 12000000 # 12582912 is the formal limit, but this gives some leeway when there's additional text

revisions_chunks_extended = list()

splits = False
for chunk in revisions_chunks:
    # Calculate the size of each chunk
    chunk_size = sum([c["size"] for c in chunk])

    print(chunk_size, api_limit)
    if chunk_size > api_limit:
        # If a chunk is too large, split it into two and create a new chunk list
        splits = True
        print("Chunk size exceeds API limit")
        chunk1 = chunk[:len(chunk)//2]
        chunk2 = chunk[len(chunk)//2:]
        revisions_chunks_extended.append(chunk1)
        revisions_chunks_extended.append(chunk2)
    else:
        revisions_chunks_extended.append(chunk)

if splits:
    # If there are splits, the new list will contain them
    revisions_chunks = revisions_chunks_extended

revids_chunks = list()

for chunk in revisions_chunks:
    revids_chunks.append([str(r["revid"]) for r in chunk])

json_counter = 1
contents_processed = {}

# Make API calls for 50 revisions at a time
for revids_chunk in revids_chunks:
    revids_chunk = "|".join(revids_chunk)

    print()
    print("Generating query for revision IDs: " + revids_chunk)
    print("This is for JSON counter ", str(json_counter))

    # Truncate revision IDs for testing smaller batches
    #revids = "|".join(revids.split("|")[:2])
    #print(revids)

    REV_PARAMS = {
             "action": "query",
             "prop": "revisions",
             "revids":revids_chunk,
             "rvprop": "content|ids|timestamp",
             "rvslots":rvslots,
             "formatversion": "2",
             "format": "json"
         }

    print()
    print("Query parameters:")
    print(REV_PARAMS)
    print()

    # Execute query
    q = query(REV_PARAMS)

    contents_path = os.path.join(contents_dir_raw, page_title + "_" + str(json_counter) + ".json")

    # Write query results to raw JSON file
    contents_file = open(contents_path, "w")

    # Split back up by pipes to get a list of revision IDs
    revids_chunk = revids_chunk.split("|")

    # Submit the query
    for result in q:
        # Write the raw query results to a single incremented JSON file
        # We keep this for reference
        contents_file.write(json.dumps(result,indent=5))
        print("Completed outputting raw JSON for this chunk.")
        print()

        # Write the processed query results
        # This will contain only the revision ID and the article contents
        print("Appending article content to processed data.")
        for r in range(0, len(result["pages"][0]["revisions"])):
#        for r in range(0, len(revids_chunk)):
            pages_rev = result["pages"][0]["revisions"][r]
            print("Appending revision", str(pages_rev["revid"]))
            # Check if there are deleted revisions
            # These will have the property ' "texthidden": true' instead of ["content"]
            revision_contents = pages_rev["slots"]["main"]

            if "texthidden" in revision_contents:
                print("REVISION DELETED FROM PUBLIC ARCHIVES.")
                contents_processed[str(pages_rev["revid"])]="REVISION DELETED FROM PUBLIC ARCHIVES."
            else:
                contents_processed[str(pages_rev["revid"])]=revision_contents["content"]

    contents_file.close()

    json_counter+=1

print()
print("Query submission and article content processing complete")
print("Writing article contents to file")
print()

contents_pro_path = os.path.join(contents_dir_pro, page_title + ".txt")

with open(contents_pro_path, "w") as contents_pro_file:
    contents_pro_file.write(json.dumps(contents_processed, indent=2))

contents_pro_file.close()

# Once the file contents are written, zip the JSON data and delete the individual raw JSON
zip_str = os.path.join(contents_dir_raw, page_title + ".zip") # New zip file
files_str = glob.glob(os.path.join(contents_dir_raw, page_title.replace("[","[[]").replace("]","[]]").replace("[[[]]","[[]") + "*.json")) # List of files to zip
proc_list = ["zip", zip_str] + files_str


print(proc_list)

subprocess.run(proc_list)


rm_str = glob.glob(os.path.join(contents_dir_raw, page_title.replace("[","[[]").replace("]","[]]").replace("[[[]]","[[]")) + "*json")


proc_list = ["rm"] + rm_str
print(proc_list)
subprocess.run(proc_list)

proc_list = ["gzip","--force", contents_pro_path]
print(proc_list)
subprocess.run(proc_list)

# restore print statements to terminal
sys.stdout = orig_stdout
sys.stderr = orig_stderr
logf.close()
