"""
Get revision histories from the Wikipedia API

Authorship:
- Alex Diaz-Papkovich
"""
from helper_functions import *

import argparse
import json
import os
import sys
import time

parser = argparse.ArgumentParser("Get revision history of an article.")
parser.add_argument("page_title", metavar="Page title", type=str,
                    help="The page to use.")
parser.add_argument("--out", metavar="out", dest="out_dir",
                    default="data/revision_histories",
                    help="Output directory (default data/revision_histories)")
parser.add_argument("--log", metavar="log", dest="log_dir",
                    default="logs",
                    help="Output directory (default logs")

args = parser.parse_args()

page_title = args.page_title
out_dir = args.out_dir
log_dir = args.log_dir

# Note that we can only use rvlimit with one page at a time

tstamp = time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time()))

# For consistency replace spaces with dashes
page_title = page_title.replace(" ","_")

revision_properties = "ids|timestamp|user|userid|comment|size|slotsize|tags|flags"

REV_PARAMS = {
         "action": "query",
         "prop": "revisions",
         "titles": page_title,
         "rvprop": revision_properties, #get content with "content"
         "rvslots": "main",
         "formatversion": "2",
         "format": "json",
        "rvlimit":"max"
     }

# Check for special characters in page names (some are used in page titles that are forbidden in file names)
# Note that we have to do this here as we need it in REV_PARAMS first
if any(special in page_title for special in special_chars.keys()):
    for key, val in special_chars.items():
        page_title = page_title.replace(key, val)
    f = open(os.path.join(out_dir, page_title + ".txt"), "w")
else:
    f = open(os.path.join(out_dir, page_title + ".txt"), "w")

# set up logging
log_path = os.path.join(log_dir, "log_revision_history_" + page_title + "_" + tstamp + ".txt") # Create timestamped log

orig_stdout = sys.stdout  # print() statements
orig_stderr = sys.stderr  # terminal statements
logf = open(log_path, 'w')
sys.stdout = logf
sys.stderr = logf

print("Query parameters:", REV_PARAMS)

for result in query(REV_PARAMS):
    pages = result["pages"]
    for page in pages:
        #print("Page (from query result):", page)
        revisions = page["revisions"]
        for revision in revisions:
            #print(revision)
            # Note that we must use json.dumps here instead of str()
            # If we use str() we create a string representation of a Python dict (using single quotes)
            # Properly formatted JSON requires double quotes
            f.write(json.dumps(revision))
            f.write("\n")

f.close()

sys.stdout = orig_stdout
sys.stderr = orig_stderr
logf.close()
