"""
Given a file with members of a category, systematically make API calls to extract the revision histories of each page.
There are flags for every variable.
It can also call the program to get article contents.

Right now it is only set up for namespaces 0 and 14 (Article and Category)
It will not retrieve category members that are not Wikipedia article pages or categories
Examples of excluded pages are talk pages, media, templates, and Wikipedia meta pages

Authorship:
- Alex Diaz-Papkovich
"""

#TODO: Pass the namespace list in the recursive call. Right now it just passes 0 and 14.

from helper_functions import *

import argparse
import os
import subprocess

parser = argparse.ArgumentParser(description="Get revision histories of category members.",
                                 epilog="Example text to crawl all pages and the first-level sub-category:"
                                        "\n\ncrawl_category.py Modern_human_genetic_history --ns 0 14 --depth 1")
parser.add_argument("category", metavar="Category", type=str,
                    help="The category to use.")
parser.add_argument("--ns", metavar="Namespace", type=int, nargs="+", default=0, dest="ns",
                    help="Integer list of namespaces to check.")
parser.add_argument("--catdir", metavar="Category directory", dest="cat_dir",
                    default="data/category_members",
                    help="Directory storing category member files.")
parser.add_argument("--log", metavar="Log directory", dest="log_dir",
                    default="logs",
                    help="Directory to store logs.")
parser.add_argument("--force", dest="force",
                    default=False, action="store_true",
                    help="Force overwrite of files.")
parser.add_argument("--revs", dest="revs",
                    default=False, action="store_true",
                    help="Force overwrite of revisions if force is true.")
parser.add_argument("--contents", dest="contents", 
                    default=False, action="store_true",
                    help="Force overwrite of page contents if force is true.")
parser.add_argument("--depth", dest="depth", type=int,
                    default=0,
                    help="Depth of sub-categories to crawl.")
parser.add_argument("--histdir", dest="hist_dir",
                    default="data/revision_histories",
                    help="Revision history directory")
parser.add_argument("--include", dest="inclusions", type=str, nargs="+",
                    help="List of inclusion keywords to filter categories with many articles.", default=None)
parser.add_argument("--exact_include", dest="exact_inclusions",
                    action="store_true",
                    help="Whether the keywords should be exact rather than substrings.", default=False)
parser.add_argument("--exclude", dest="exclusions", type=str, nargs="+",
                    help="List of exclusion keywords to filter categories with many articles.", default=None)
parser.add_argument("--exact_exclude", dest="exact_exclusions",
                    action="store_true",
                    help="Whether the keywords should be exact rather than substrings.", default=False)
parser.add_argument("--contentdirpro", dest="content_dir_pro",
                    default="data/revision_contents_processed",
                    help="Revision contents directory (processed).")
parser.add_argument("--contentdirraw", dest="content_dir_raw",
                    default="data/revision_contents_raw",
                    help="Revision contents directory (raw).")
parser.add_argument("--inclusion_list", dest="inclusion_list",
                    default=None,
                    help="File with a list of inclusion terms. Useful if there's a lot of them, or if you want a large allow-list.")
parser.add_argument("--skip_stubs", dest="skip_stubs",
                    action="store_true",default=False,
                    help="Skip stub categories, which are automatically populated and can be quite large.")
parser.add_argument("--skip_download", dest="skip_download",
                    action="store_true", default=False,
                    help="Skip downloading page information (i.e. just retrieve category membership).")
parser.add_argument("--test", dest="test_flag", action="store_true",
                    help="When enabled will not scrape revisions.")
# for python 3.9+
#parser.add_argument("--test", dest="test_flag", action=argparse.BooleanOptionalAction,
#                    help="When enabled will not scrape revisions.")


args = parser.parse_args()

cat = args.category
ns = args.ns
cat_dir = args.cat_dir
log_dir = args.log_dir
revs = args.revs
force = args.force
depth = args.depth
contents = args.contents
hist_dir = args.hist_dir
inclusions = args.inclusions
exclusions = args.exclusions
content_dir_pro = args.content_dir_pro
content_dir_raw = args.content_dir_raw
inclusion_list = args.inclusion_list
exact_inclusions = args.exact_inclusions
exact_exclusions = args.exact_exclusions
skip_stubs = args.skip_stubs
skip_download = args.skip_download

test = args.test_flag

tstamp = time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time())) # For logging purposes

cat_path = os.path.join(cat_dir, cat + ".txt")

log_path = os.path.join(log_dir, "log_category_crawl_" + cat + "_" + tstamp + ".txt")

# Set up logging.
orig_stdout = sys.stdout  # print() statements
orig_stderr = sys.stderr  # terminal statements
logf = open(log_path, 'w')
sys.stdout = logf
sys.stderr = logf

if inclusion_list is not None:
    with open(inclusion_list, "r") as f:
        allowed = f.read().strip().split("\n")

    if inclusions is None:
        inclusions  = allowed.copy()
    else:
        inclusions+= allowed

# Create output directory if it doesn't already exist
if not os.path.exists(cat_dir):
    print("Category directory does not exist.")
    print("Creating category directory:", cat_dir)
    os.mkdir(cat_dir)

# List of all members of a category that fall within the given namespaces
if os.path.exists(cat_path):
    # Check if a file listing the category members already exists
    # If not, create it
    # If it does, open it and identify the category members
    print("Category file exists, using members listed in", cat_path)
    print()
    members = parse_category_members(cat_path, ns)
else:
    print("Category file does not exist, retrieving category members.")
    subprocess.run(["python", "get_category_members.py", cat, "--out", cat_dir])
    print("Category file created, using members listed in", cat_path)
    print()
    members = parse_category_members(cat_path, ns)

for member in members:
    # Loop through the category members
    print("Currently checking JSON item", member)
    print()

    if member["ns"] in ns:
        # Make sure we're using namespaces that we want
        if member["ns"]==14 and depth > 0:
            # Check if we are in a category and have valid depth
            subcat = member["title"].split("Category:")[1].replace(" ","_")

            if skip_stubs and subcat.endswith("_stubs"):
                # Skip categories
                print("skip_stubs activated, skipping category of stubs.")
            else:
                # Get the sub-category members
                subprocess.run(["python", "get_category_members.py", subcat])
    
                # Create base command to crawl the sub-category
                cmd = ["python", "crawl_category.py", subcat, "--ns", "0", "14", "--depth", str(depth - 1),
                       "--catdir",cat_dir,
                       "--contentdirpro", content_dir_pro,
                       "--contentdirraw", content_dir_raw,
                       "--histdir", hist_dir,
                       "--log", log_dir]
    
                # Pass inclusion/exclusion lists
                if inclusions is not None:
                    cmd = cmd + ["--include"] + inclusions
    
                if exclusions is not None:
                    exclude = cmd + ["--exclude"] + exclusions

                # Pass boolean parameters
                if force:
                    cmd = cmd + ["--force"]
    
                if test:
                    cmd = cmd + ["--test"]
    
                if exact_inclusions:
                    cmd = cmd + ["--exact_include"]
    
                if exact_exclusions:
                    cmd = cmd + ["--exact_exclude"]

                if skip_stubs:
                    cmd = cmd + ["--skip_stubs"]

                if skip_download:
                    cmd = cmd + ["--skip_download"]
    
                # redundant because the inclusion_list elements are used in the --include flag above
                #if inclusion_list is not None:
                #    cmd = cmd + ["--inclusion_list", inclusion_list]
    
                print("Depth is >0, beginning sub-category crawl.")
                print("Sub-category:", subcat)
                print("Sub-category log will continue in separate log file.")
                print()
                print("Printing command parameters:")
                print(cmd)
    
                subprocess.run(cmd)
    
                print("Sub-category crawl complete.")
        elif member["ns"]==14:
            print("Depth is set to 0, skipping sub-category crawl.")
            print()

        if test:
            print("Test flag detected, skipping article revision/contents.")
            print()
            continue

        if skip_download:
            print("Skip download flag detected.")

        if member["ns"]!=14 and not skip_download:
            # If forced overwrite is specified just run the programs
            # Otherwise check if the files exist
            # If they exist, skip them
            # For test runs, skip the scrape

            # Check if the page is in the exclusions or inclusions list
            # Also see if we want exact inclusions/exclusions, or just filter out based on keywords
            if exact_exclusions:
                exclude_page = (exclusions is not None and any(
                    exc==member["title"].replace(" ", "_") for exc in exclusions))
            else:
                exclude_page = (exclusions is not None and any(
                    exc in member["title"].replace(" ", "_") for exc in exclusions))

            if exact_inclusions:
                include_page = (
                            inclusions is None or any(inc==member["title"].replace(" ", "_") for inc in inclusions))
            else:
                include_page = (
                            inclusions is None or any(inc in member["title"].replace(" ", "_") for inc in inclusions))

            if force:
                print("Force specified. Will overwrite files.")
                print()

                if revs:
                    if include_page and not exclude_page:
                    # Get revision histories
                    # If we specify to look for keywords in article titles, look for them
                    # Otherwise, just make the API calls for every article
                        print("Getting revision history for page in inclusion list:", member["title"])
                        print()
                        subprocess.run(["python", "get_revision_history.py", member["title"],
                                        "--out", hist_dir, "--log", log_dir])
                    else:
                        print("Inclusion/exclusion criteria not met, skipping file.")
                        print("Page inclusion:", include_page)
                        print("Page exclusion:", exclude_page)

                if contents:
                    # Get article contents
                    if include_page and not exclude_page:
                        print("Getting contents for page in inclusion list:", member["title"])
                        print()
                        subprocess.run(["python", "get_article_contents.py", member["title"],
                                        "--out_raw", content_dir_raw, "--out_pro", content_dir_pro,
                                        "--rev_dir", hist_dir, "--log", log_dir])
                    else:
                        print("Inclusion/exclusion criteria not met, skipping file.")
                        print("Page inclusion:", include_page)
                        print("Page exclusion:", exclude_page)

            else:
                print("Checking if the following path exists:")
                print(os.path.join(hist_dir, member["title"].replace(" ", "_") + ".txt"))
                print()

                # Check if there is a revision history file
                if not os.path.exists(os.path.join(hist_dir, member["title"].replace(" ", "_") + ".txt")):
                    # If the file of revision histories does not exist, make the API calls and retrieve it
                    if include_page and not exclude_page:
                        print("Getting revision history for page in inclusion list:", member["title"])
                        print()
                        subprocess.run(["python", "get_revision_history.py", member["title"],
                                        "--out", hist_dir, "--log", log_dir])
                    else:
                        print("Inclusion/exclusion criteria not met, skipping file.")
                        print("Page inclusion:", include_page)
                        print("Page exclusion:", exclude_page)

                else:
                    print("Revision history exists, skipping this page.")

                print("Checking if the following paths exists:")
                print(os.path.join(content_dir_pro, member["title"].replace(" ", "_") + ".txt"))
                print(os.path.join(content_dir_pro, member["title"].replace(" ", "_") + ".txt.gz"))
                print()

                # Check if there is a revision contents file
                if not os.path.exists(os.path.join(content_dir_pro, member["title"].replace(" ", "_") + ".txt")) and \
                        not os.path.exists(os.path.join(content_dir_pro, member["title"].replace(" ", "_") + ".txt.gz")):
                    # If the file of processed revision contents does not exist, make the API calls and retrieve it

                    if include_page and not exclude_page:
                        print("Getting revision history for page in inclusion list:", member["title"])
                        print()
                        subprocess.run(["python", "get_article_contents.py", member["title"],
                                        "--out_raw", content_dir_raw, "--out_pro", content_dir_pro,
                                        "--rev_dir", hist_dir, "--log", log_dir])
                    else:
                        print("Inclusion/exclusion criteria not met, skipping file.")
                        print("Page inclusion:", include_page)
                        print("Page exclusion:", exclude_page)
                else:
                    print("Processed article contents exist, skipping this page.")
                    print()

print("Done crawling category", cat)

sys.stdout = orig_stdout
sys.stderr = orig_stderr
logf.close()