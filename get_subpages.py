"""
Gets all subpages of a page. The example is for a talk page but this also works with regular pages.

Authorship:
- Alex Diaz-Papkovich
"""

from helper_functions import *

import argparse
import json
import re
import subprocess

"""
Test script:
python get_subpages.py Talk:Canadians \
--out_raw data/talk_pages/revision_contents_raw \
--out_pro data/talk_pages/revision_contents_processed \
--rev_dir data/talk_pages/revision_histories \
--log logs
"""

parser = argparse.ArgumentParser("Get contents of every revision of a page and its subpages (including archives).")
parser.add_argument("page_title", metavar="Page title", type=str,
                    help="The page to retrieve.")
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
parser.add_argument("--subfolders", metavar="subfolders", dest="subfolders",
                    default=True,
                    help="Flag for whether to create subfolders in output folders. Otherwise use specified directories.")

args = parser.parse_args()

page_title = args.page_title

contents_dir_raw = args.contents_dir_raw
contents_dir_pro = args.contents_dir_pro
revisions_dir = args.revisions_dir

log_dir = args.log_dir
subfolders = args.subfolders

# Create directories for files
os.makedirs(os.path.join(revisions_dir), exist_ok=True)
os.makedirs(os.path.join(contents_dir_raw), exist_ok=True)
os.makedirs(os.path.join(contents_dir_pro), exist_ok=True)

print("Getting the target page first.")

print("Getting revision history.")

# Get the target page first
subprocess.run(
    ["python", "get_revision_history.py", page_title,
     "--out", revisions_dir,
     "--log", log_dir]
)

print("Getting page contents.")

subprocess.run(
    ["python", "get_article_contents.py", page_title,
     "--out_raw", contents_dir_raw,
     "--out_pro", contents_dir_pro,
     "--rev_dir", revisions_dir,
     "--log", log_dir]
)

# Now begin work on the subpages
# Subpages are stored as a dict with {ns, title, pageid} variables
print("Getting subpages.")
subpages = get_subpages(page_title)

# Replace special characters for filenames
if any(special in page_title for special in special_chars.keys()):
    for key, val in special_chars.items():
        page_title = page_title.replace(key, val)

page_title = page_title.replace(" ","_")

# Print subpage data to log
with open(os.path.join(log_dir, "subpages_" + page_title + ".txt"), "w") as log_file:
    for subpage in subpages:
        log_file.write(json.dumps(subpage, indent=2))

log_file.close()

# Get revisions and contents for each page
# First make sure there are directories to use
if subfolders:
    subpages_revisions_dir = os.path.join(revisions_dir, "subpages", page_title)
    os.makedirs(subpages_revisions_dir, exist_ok=True)

    subpages_contents_dir_raw = os.path.join(contents_dir_raw, "subpages", page_title)
    os.makedirs(subpages_contents_dir_raw, exist_ok=True)

    subpages_contents_dir_pro = os.path.join(contents_dir_pro, "subpages", page_title)
    os.makedirs(subpages_contents_dir_pro, exist_ok=True)
else:
    subpages_revisions_dir = revisions_dir
    subpages_contents_dir_raw = contents_dir_raw
    subpages_contents_dir_pro = contents_dir_pro

titles = list()
page_ids = list()

# Get the revisions and contents for each subpage
for subpage in subpages:
    titles.append(subpage["title"])
    page_ids.append(subpage["pageid"])

    print("Working on subpage.")
    print(subpage)
    print("Getting revision history.")

    subprocess.run(
        ["python", "get_revision_history.py", subpage["title"],
         "--out", subpages_revisions_dir,
         "--log", log_dir]
    )

    print("Getting page contents.")

    subprocess.run(
        ["python", "get_article_contents.py", subpage["title"],
        "--out_raw", subpages_contents_dir_raw,
         "--out_pro", subpages_contents_dir_pro,
         "--rev_dir", subpages_revisions_dir,
         "--log", log_dir]
    )