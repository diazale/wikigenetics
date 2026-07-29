"""
A variety of helper functions that I use.
Much of it is copied or based on the official Mediawiki API resources.

Authorship:
- Alex Diaz-Papkovich
"""

import json
import os
import requests
import sys
import time

# Special characters like : and / appear in some article titles, so we replace them
# These special characters are not allowed in file names or directories
special_chars = {
    ":":"[COLON]",
    "/":"[FORWARDSLASH]",
    "\\":"[BACKSLASH]",
    "<":"[GREATERTHAN]",
    ">":"[LESSTHAN]",
    "\"":"[DOUBLEQUOTE]",
    "|":"[PIPE]",
    "?":"[QMARK]",
    "!":"[EMARK]",
    "*":"[ASTERISK]"
}

# Namespaces are stored as numbers, translate these to human terms
ns_dict = {
    0:"Main/Article",
    1:"Talk",
    2:"User",
    3:"User talk",
    4:"Wikipedia",
    5:"Wikipedia talk",
    6:"File",
    7:"File talk",
    8:"MediaWiki",
    9:"MediaWiki talk",
    10:"Template",
    11:"Template talk",
    12:"Help",
    13:"Help talk",
    14:"Category",
    15:"Category talk",
    100:"Portal",
    101:"Portal talk",
    118:"Draft",
    119:"Draft talk",
    710:"TimedText",
    711:"TimedText talk",
    828:"Module",
    829:"Module talk"
}

def query(request, headers=""):
    """
    This will retrieve all query results, incorporating the lastContinue parameter which lets us retrieve everything

    From https://www.mediawiki.org/wiki/API:Continue
    :param request: dictionary of request parameters
    :param headers: dictionary User-agent information e.g. {"User-Agent":"MyBot/0.3 (me@email.com)"}
    :return: results of the query
    """

    request['action'] = 'query'
    request['format'] = 'json'
    lastContinue = {}
    while True:
        # Clone original request
        req = request.copy()
        # Modify it with the values returned in the 'continue' section of the last result.
        req.update(lastContinue)
        # Call API
        result = requests.get('https://en.wikipedia.org/w/api.php', params=req, headers=headers).json()
        if 'error' in result:
            print('Error in request')
            print('Request', request)
            raise Exception(result['error'])
        if 'warnings' in result:
            print('Warning in request')
            print('Request', request)
            print(result['warnings'])
        if 'query' in result:
            yield result['query']
        if 'continue' not in result:
            break
        lastContinue = result['continue']

def parse_revision_history(rev_file):
    """
    Given a file of revision histories, parse the JSON and return information.

    This works with text files of JSON data.
    Assume each line is JSON. The file itself is *not* JSON, but a text file.

    Currently article history files contain:
    * revid - revision ID
    * parentid - parent revision ID (0 if article is new)
    * minor - boolean to indicate minor edit
    * user - name of user who made the edit
    * userid - ID of user
    * timestamp - time and date in YYYY-MM-DD[T]HH:MM:SS format (ISO 8601)
    * size - article size in bytes

    :param file containing lines of revision history
    :return: returns a list of dicts
    """

    f = open(rev_file, "r")
    revisions = f.read().rstrip().split("\n")
    f.close()

    parsed_list = list()

    for revision in revisions:
        rj = json.loads(revision)

        parsed_list.append(rj)

    return parsed_list

def get_revision_history(page_title, out_dir, log_dir):
    """
    Given a page title, retrieve all of its revisions.
    Requires a log and output directory
    Special characters in page names will be replaced.

    :param page_title: String
    :param out_dir: Directory to store output
    :param log_dir: Directory to store logs
    :return: Outputs a file containing all revisions of a page.
    """
    tstamp = time.strftime('%Y%m%d_%H%M%S', time.localtime(time.time()))

    page_title = page_title.replace(" ", "_")

    revision_properties = "ids|timestamp|user|userid|comment|size|slotsize|tags|flags"

    REV_PARAMS = {
        "action": "query",
        "prop": "revisions",
        "titles": page_title,
        "rvprop": revision_properties,  # get content with "content"
        "rvslots": "main",
        "formatversion": "2",
        "format": "json",
        "rvlimit": "max"
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
    log_path = os.path.join(log_dir, "log_contents_" + page_title + "_" + tstamp + ".txt")  # Create timestamped log

    orig_stdout = sys.stdout  # print() statements
    orig_stderr = sys.stderr  # terminal statements
    logf = open(log_path, 'w')
    sys.stdout = logf
    sys.stderr = logf

    print("Query parameters:", REV_PARAMS)

    for result in query(REV_PARAMS):
        pages = result["pages"]
        for page in pages:
            # print("Page (from query result):", page)
            revisions = page["revisions"]
            for revision in revisions:
                # print(revision)
                # Note that we must use json.dumps here instead of str()
                # If we use str() we create a string representation of a Python dict (using single quotes)
                # Properly formatted JSON requires double quotes
                f.write(json.dumps(revision))
                f.write("\n")

    f.close()

    sys.stdout = orig_stdout
    sys.stderr = orig_stderr
    logf.close()

def get_external_url_usage(search_url):
    """
    Return all pages containing given external link

    :param search_url: URL to search, without the protocol (assumes http/s by default)
    :return: Returns a list of all API query results
    """

    PARAMS = {
        "action": "query",
        "format": "json",
        "list": "exturlusage",
        "eunamespace": "*",
        "euquery": search_url,
        "eulimit":"500"
    }

    EXTURLS = list()

    for result in query(PARAMS):
        EXTURLS.append(result["exturlusage"])

    return(EXTURLS)

def get_redirects(page_titles, ns="0"):
    """
        get_redirects.py

        MediaWiki API Demos
        Demo of `Redirects` module: Get all redirects to the given page(s)

        MIT License

        :param page_titles: Titles of pages (pipe-separated if multiple)
        :param ns: namespace codes (pipe-separated if multiple)

        :return: JSON file of all redirects to specified pages
    """

    import requests

    S = requests.Session()

    URL = "https://en.wikipedia.org/w/api.php"

    PARAMS = {
        "action": "query",
        "format": "json",
        "titles": page_titles,
        "prop": "redirects",
        "rdnamespace":ns,
        "rdlimit":"max"
    }

    REDIRECTS = list()

    for result in query(PARAMS):
        REDIRECTS.append(result)

    return(REDIRECTS)

def get_subpages(page_title, pslimit=500):
    """
    Get all subpages for an input page
    This is being set up for archives of talk pages but can be used in general.

    Note the documentation that this does not strictly retrieve prefix pages
    It will avoid redirects and take other heuristics into account to detect pages
    https://www.mediawiki.org/wiki/API:Prefixsearch

    :param page_title: Page for which we want the subpages
    :param pslimit: Number of prefix pages to return (defaults to max, 500)

    :return: Returns a list of subpages
    """

    page_title = page_title + "/"

    PARAMS = {
        "action": "query",
        "format": "json",
        "list": "prefixsearch",
        "pssearch": page_title,
        "pslimit":pslimit
    }

    PFIX = list()

    for result in query(PARAMS):
        pages = result["prefixsearch"]
        for page in pages:
            PFIX.append(page)
        #PFIX.append(result['prefixsearch'])

    return(PFIX)


def parse_category_members(category_file, ns, verbose=True):
    """
    Parse a file containing query results from get_category_members.py
    Each line should be a JSON object with three parameters: pageid, ns, title
    ns 0 is the article space
    ns 14 is categories

    :param category: The category file to look at (substitute _ for space)
    :param ns: List of ints, namespaces to look at (0 is article space, 14 is categories)
    :return: Returns a list of all titles in the provided name spaces for a category
    """
    if verbose:
        print("Preparing to read category file:", category_file)
    f = open(category_file, "r")
    members = f.read().rstrip().split("\n")
    f.close()

    member_list = list()

    for member in members:
        member = json.loads(member)
        member_list.append(member)
    
    if verbose:
        print("Member list generated.")
    return member_list


def get_page_categories(instr):
    """
    Given a page revision, identify and extract the categories used.
    It parses the data for text of the form [[Category:*|]] and returns the *

    :param instr: String. Input data, probably a page revision.
    :return: List of all categories used
    """

    cats = list()
    cat_start = 0

    while cat_start > -1:
        # Find the first category
        cat_start = instr.find("[[Category:")

        if cat_start == -1:
            # No more categories found, exit function
            return cats

        cat_end = instr[cat_start:].find("]]")

        cat = instr[cat_start:cat_start + cat_end]
        cat = cat.split("[[Category:")[1]  # Trim the "Category:" tag
        cat = cat.split("|")[0]  # Trim the sorting value, if it exists

        cats.append(cat)
        instr = instr[cat_start + cat_end:]

    return cats

def gen_url(rev_id, prev=False, next=False, curr=False):
    """
    Generate a Wikipedia URL based upon a revision ID

    Options:
    - prev to compare to previous revision
    - next to compare to next revision
    - curr to compare to current revision
    """
    url_ = "https://en.wikipedia.org/wiki/index.php?oldid=" + str(rev_id)
    if prev:
        url_+= "&diff=prev"
    elif curr:
        url_+= "&diff=curr"
    elif next:
        url_+= "&diff=next"

    return url_
