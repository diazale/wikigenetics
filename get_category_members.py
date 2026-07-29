# https://www.mediawiki.org/wiki/API:Categorymembers
"""
Given a category, return all of its members
This includes all types of pages (e.g. user pages and sub-categories)
Categories may not immediately populate if there have been recent changes or page moves.

Authorship:
- Alex Diaz-Papkovich
"""

from helper_functions import query

import argparse
import json
import os

parser = argparse.ArgumentParser("Get category members.")
parser.add_argument("category", metavar="Category", type=str,
                    help="The category to check for pages.")
parser.add_argument("--out", metavar="out", dest="out_dir",
                    default="data/category_members",
                    help="Output directory (default data/category_members)")

args = parser.parse_args()

category = args.category.replace(" ","_")

out_dir = args.out_dir

PARAMS = {
    "action": "query",
    "cmtitle": "Category:" + category,
    "cmlimit": "max",
    "list": "categorymembers",
    "format": "json"
}

f = open(os.path.join(out_dir, category + ".txt"), "w")

for result in query(PARAMS):
    for page in result["categorymembers"]:

        f.write(json.dumps(page))
        f.write("\n")

f.close()