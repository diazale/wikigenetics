"""
This script downloads pageviews from the Wikimedia API.

The API does not like fielding multiple requests so workers are set to 1.
It may also just fail so you would have to double-check and run again.

Authorship:
- Alex Diaz-Papkovich
"""

import argparse
import json
import os
import requests
import time
import urllib
from concurrent.futures import ThreadPoolExecutor

tstamp = time.strftime('%Y%m%d_%H%M%S',time.localtime(time.time()))

# documentation:
# https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html
project = "en.wikipedia.org"
access = "all-access" # all-access ┃ desktop ┃ mobile-app ┃ mobile-web
agent = "user" #  all-agents ┃ user ┃ spider ┃ automated
page_name = "Canadians"
granularity = "daily" # daily ┃ monthly
start = "2025010100" # YYYYMMDDHH - first day and hour to include
end = "2025123100" # YYYYMMDDHH - last day and hour to include

max_workers = 1

# Output directory
output_dir = ""

# txt file listing pages to query
in_file = ""

# Check the already-downloaded pages
already_downloaded = set([p.split(".json")[0].replace(" ","_") for p in os.listdir(output_dir)])

with open(in_file, "r") as f:
    #pages = [p.split(".txt")[0] for p in f.read().strip().split("\n")] # downloaded are listed as txts
    pages = [p.replace(" ","_").replace("[COLON]",":") for p in f.read().strip().split("\n")]

temp = []

for page in pages:
    if page not in already_downloaded:
        temp.append(page)

pages = temp.copy()

print(len(pages))

# The API is free but requires identification
headers = {"User-Agent": "bot_name (your_email@example.com)"}

def construct_api_url(project_, access_, agent_, page_, granularity_, start_, end_):
    """
    Function to take the inputs and construct an API URL for each page specified

    :param project_: e.g. en.wikipedia.org
    :param access_: all-access, desktop, mobile-app, mobile-web
    :param agent_: all-agents, user, spider, automated
    :param page_: Wikipedia page title
    :param granularity_: daily, monthly
    :param start_: YYYYMMDDHH
    :param end_: YYMMDDHH
    :return: API URL
    """
    return "/".join(["https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article",
                   project_,access_,agent_,urllib.parse.quote(page_),granularity_,start_,end_])

def get_and_save_request(indexed_api_url_, headers_=headers):
    """
    Worker function to make the API request and save the data to file

    :param api_url_: URL for the request
    :param headers_: Agent headers
    :return: Returns the JSON for the call
    """
    page_name = indexed_api_url_[0]
    api_url_ = indexed_api_url_[1]
    output_dir_ = indexed_api_url_[2]

    json_data = requests.get(api_url_, headers=headers_).json()

    output_path = os.path.join(output_dir_, page_name + ".json")

    f = open(output_path, "w")
    f.write(json.dumps(json_data))
    f.close()

# Construct the API url for each of the pages requested
# Store as a tuple with extra information for the worker function
indexed_api_urls = [(page,
                     construct_api_url(project, access, agent, page, granularity, start, end),
                     output_dir) for page in pages]

# Try slowing down the requests
step = 200
num_urls = len(indexed_api_urls)

for i in range(0, num_urls, step):
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.map(get_and_save_request, indexed_api_urls[i:i+step])

    time.sleep(1)

