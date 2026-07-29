"""
This script creates SQL databases out of revision histories, page metadata, page keywords,
users, categories, and sections.

The SQL approach initially saved time compared to loading in text files.
Eventually we started using parquet data formats as they were far quicker for loading.

Authorship:
- Abigal Kuntzleman
- ChatGPT 4.1
"""

from sqlalchemy import create_engine, ForeignKey, String, Integer, Column, Boolean, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import sqlalchemy.orm
import json
import os
import gzip
from sqlalchemy.exc import IntegrityError
import argparse
import wikitextparser as wtp
import time
from sqlalchemy import inspect

#Set the directory 
directory = '.../wikipedia/data'
#ORDER TO RUN IT IN: revision_histories, page_metadata, page_keywords, users, categories_revisions, sections
parser = argparse.ArgumentParser("Load a new table.")
parser.add_argument("data_folder", metavar="Folder with data", type=str, help="Folder containing the data for all contents - subfolders should include revision_histories, databases, etc")
parser.add_argument("table", metavar="Table to populate", type=str, help="Name of the table to overwrite. Options are revision_histories, page_metadata, page_keywords, users")

n_lines_to_add = 50_000

#NOTE: i updated this so that each function separately accesses its own session instead of using the same global session
# hopefully this means things are parallelizable
args = parser.parse_args()

directory = args.data_folder
table = args.table

if table not in ['revision_histories','users','page_metadata','page_keywords', 'categories_revisions','create_user_list', 'sections']:
    raise argparse.ArgumentTypeError('Table must be one of the following: revision_histories, users, page_metadata, page_keywords, categories_revisions, sections')


#Setting up the database and all the tables
Base = sqlalchemy.orm.declarative_base()

#TODO: Generalize the databases
#Defining the attributes of the revision_histories table
class revision_histories(Base):
    __tablename__ = "revision_histories"
    page_name = Column('page_name', ForeignKey("page_metadata.page"))
    revision_id = Column("revision_id", Integer, primary_key=True)
    parent_id = Column("parent_id", Integer)
    minor = Column("minor", Boolean)
    user = Column("user", String)
    user_id = Column("user_id", String, ForeignKey("users.user_id"))
    timestamp = Column("timestamp", String)
    size = Column("size", Integer)
    comment = Column("comment", String)
    tags = Column("tags", String)

    def __init__(self, page_name, revision_id, parent_id, minor, user,
                    user_id, timestamp, size, comment, tags):
        self.page_name = page_name
        self.revision_id = revision_id
        self.parent_id = parent_id
        self.minor = minor
        self.user = user
        self.user_id = user_id
        self.timestamp = timestamp
        self.size = size
        self.comment = comment
        self.tags = tags

#Defining the attributes of the page_metadata table
class page_metadata(Base):
    __tablename__ = "page_metadata"
    page = Column('page', String, primary_key = True)
    keywords = Column('keywords', String)
    keywords_mentioned = Column('keywords_mentioned', Boolean)
    keyword_earliest_mention = Column('keyword_earliest_mention', String)
    keyword_earliest_revision = Column('keyword_earliest_revision', String)
    keyword_latest_mention = Column('keyword_latest_mention', String)
    keyword_latest_revision = Column('keyword_latest_revision', String)
    earliest_revision = Column('earliest_revision', String)
    latest_revision = Column('latest_revision', String)

    def __init__(self, page, keywords, keywords_mentioned, keyword_earliest_mention, keyword_earliest_revision,
    keyword_latest_mention, keyword_latest_revision, earliest_revision, latest_revision):
        self.page = page
        self.keywords = keywords
        self.keywords_mentioned = keywords_mentioned
        self.keyword_earliest_mention = keyword_earliest_mention
        self.keyword_earliest_revision = keyword_earliest_revision
        self.keyword_latest_mention = keyword_latest_mention
        self.keyword_latest_revision = keyword_latest_revision
        self.earliest_revision = earliest_revision
        self.latest_revision = latest_revision

class page_keywords(Base):
    __tablename__ = "page_keywords"
    revision_id = Column('revision_id', ForeignKey("revision_histories.revision_id"), primary_key = True)
    keyword = Column("keyword", String, primary_key = True)
    count = Column("count", Integer)

    def __init__(self, revision_id, keyword, count):
        self.revision_id = revision_id
        self.keyword = keyword
        self.count = count


class users(Base):
    __tablename__ = "users"
    user_id = Column("user_id", String, primary_key = True)
    user = Column("user", String)
    edit_count = Column("edit_count", Integer)
    registration = Column("registration", String)

    def __init__(self, user_id, user, edit_count, registration):
        self.user_id = user_id
        self.user = user
        self.edit_count = edit_count
        self.registration = registration

class categories_revisions(Base):
    __tablename__ = 'categories_revisions'
    revision_id = Column('revision_id', ForeignKey(revision_histories.revision_id), primary_key = True)
    category = Column('category', String)

    def __init__(self, revision_id, category):
        self.revision_id = revision_id
        self.category = category

class sections(Base):
    __tablename__ = "sections"
    revision_id = Column('revision_id', String, primary_key = True)
    section_title = Column('section_title', String, primary_key = True)
    section_rank = Column('section_rank', String, primary_key = True)
    section_level = Column('section_level', String)
    keyword_ever_mentioned = Column('keyword_ever_mentioned', Boolean)

    def __init__(self, revision_id, section_title, section_rank, section_level, keyword_ever_mentioned):
        self.revision_id = revision_id
        self.section_title = section_title
        self.section_rank = section_rank
        self.section_level = section_level
        self.keyword_ever_mentioned = keyword_ever_mentioned

#Connect to the database
db = "sqlite:.../wikipedia-final.db"

engine = create_engine(db)
Base.metadata.create_all(bind=engine)

#Begin the database
Session = sessionmaker(bind=engine)

session = Session()

#A helper function to bulk insert data; on exception, insert until error row is caught
def smooth_bulk_insert(curr_table, data):
    print(f'Ready to commit {len(data)} lines\n')
    try:
        session.bulk_insert_mappings(curr_table, data)
        session.commit()
    except Exception as e:
        session.rollback()
        for row in data:
            try:
                session.add(curr_table(**row))
                session.commit()
            except IntegrityError as err:
                session.rollback()
                print(f"Error at this row {row}: \n Error: {err}")
    finally:
        session.close()
        print(f'Committed. Reset log to {len(data)} lines\n')

# Grabs all the users from a particular table, outputs them to users_in_table.txt
def grab_users_from_table(table):
    user_lits = []
    users = session.query(table.user, table.user_id).group_by(table.user).all()
    with open('users_in_table.txt','w') as user_file:
        for user in users:
            user_lits.append(user[0] + '\n')
            if len(user_lits) >= n_lines_to_add:
                user_file.writelines(user_lits)
                user_lits = []
        if len(user_lits) > 0:
            user_file.writelines(user_lits)

skip_pages = [] # pages to skip (also ended up being obsolete)

# this ended up being obsolete, keeping for posterity
genetics_terms = ["admix","genetic", "haplo", "principal component", "mitochondria", "autosom", "chromosom", 
                  "mtdna","mt-dna","genom","pca plot"]

def is_in_skip_pages(name):
    for each in skip_pages:
        if each in name:
            return True
    return False

def overwrite_categories_revisions():
    session.query(categories_revisions).delete()
    session.commit()
    revision_to_cat = dict()
    for cat_name in os.listdir(directory + '/category_members'):
        if '.txt' in cat_name and not is_in_skip_pages(cat_name):
            with open(os.path.join(directory + '/category_members', cat_name)) as cat_file:
                for line in cat_file:
                    line = json.loads(line)
                    page_name = line['title'].replace(' ', '_')
                    for rev_page in os.listdir(directory + '/revision_histories'):
                        if rev_page[:-4] == page_name:
                            with open(os.path.join(directory + '/revision_histories', rev_page)) as revision_file:
                                for rev_line in revision_file:
                                    rev_line = json.loads(rev_line)
                                    if rev_line['revid'] not in revision_to_cat:
                                        revision_to_cat[rev_line['revid']] = f'{cat_name[:-4]}'
                                    else:
                                        revision_to_cat[rev_line['revid']] += f':{cat_name[:-4]}'
    data_to_add = []
    for k, v in revision_to_cat.items():
        data_to_add.append({'revision_id': k, 'category': v})
        if len(data_to_add) >= n_lines_to_add:
            smooth_bulk_insert(categories_revisions, data_to_add)
            data_to_add = []
    if len(data_to_add) > 0:
        smooth_bulk_insert(categories_revisions, data_to_add)


#Overwriting the table revision_histories
def overwrite_revision_histories():
    session.query(revision_histories).delete()
    session.commit()
    filtered_data = []
    for name in os.listdir(directory + '/revision_histories'):
        if '.txt' in name and not is_in_skip_pages(name):
            print(name)
            with open(os.path.join(directory + '/revision_histories', name)) as revFile:
                for line in revFile:
                    filtered_line = {}
                    row = json.loads(line)
                    #handling the list of tags to be a colon-delimited string
                    tags = row['tags']
                    tagString = ''
                    if len(tags) > 0:
                        for tag in tags[:-1]:
                            tagString += tag
                            tagString += ':'
                        tagString += tags[-1]
                    filtered_line['tags'] = tagString

                    #Handling the userID which is sometimes not there
                    if 'userhidden' in row.keys():
                        if row['userhidden'] == True:
                            username = 'UserHidden'
                            userID = 'UserHidden'
                        else:
                            print('THERE IS A HIDDEN USER WITH USERHIDDEN TAG SET TO FALSE')
                    else:
                        username = row['user']
                        if row['userid'] == 0:
                            userID = '_'.join(map(str, row['user'].split('.')))
                        else:
                            userID = row['userid']
                    filtered_line['user_id'] = userID
                    filtered_line['user'] = username

                    #Handling the comments which are sometimes not there
                    if 'commenthidden' in row.keys():
                        if row['commenthidden'] == True:
                            usercomment = 'CommentHidden'
                        else:
                            print('THERE IS A HIDDEN COMMENT WITH COMMENTHIDDEN TAG SET TO FALSE')
                    else:
                        usercomment = row['comment']
                    filtered_line['comment'] =  usercomment

                    filtered_line['page_name'] = name[:-4]
                    filtered_line['revision_id'] = row['revid']
                    filtered_line['parent_id'] = row['parentid']
                    filtered_line['minor'] = row['minor']
                    filtered_line['timestamp'] = row['timestamp']
                    filtered_line['size'] = row['size']
                    filtered_data.append(filtered_line)

                    if len(filtered_data) >= n_lines_to_add:
                        smooth_bulk_insert(revision_histories, filtered_data)
                        filtered_data = []
    if len(filtered_data) > 0:
        smooth_bulk_insert(revision_histories, filtered_data)

#Creating the pages metadata table
def overwrite_page_metadata():
    session.query(page_metadata).delete()
    session.commit()
    metadata_data = []
    for keywords in os.listdir(directory + '/keyword_results'):
        if not is_in_skip_pages(keywords):
            with open(os.path.join(directory + '/keyword_results', keywords)) as keywordFile:
                keys = keywordFile.read()
                try:
                    res = json.loads(keys)
                    if not isinstance(res, dict):
                            print(f"Not a JSON object: {os.path.join(directory + '/keyword_results', keywords)}")

                except json.JSONDecodeError:
                    print(f"Invalid JSON: {os.path.join(directory + '/keyword_results', keywords)}")

                try:
                    this_row = {}
                    all_keywords = res['keywords']
                    keyString = ''
                    for keys in all_keywords[:-1]:
                        keyString += keys
                        keyString += ':'
                    keyString += all_keywords[-1]
                    this_row['keywords'] = keyString
                    this_row['page'] = res['page']
                    this_row['keywords_mentioned'] = res['keywords_ever_mentioned']
                    this_row['keyword_earliest_mention'] = res['keywords_earliest_mention']
                    this_row['keyword_earliest_revision'] = res['keywords_earliest_revision']
                    this_row['keyword_latest_mention'] = res['keywords_latest_mention']
                    this_row['keyword_latest_revision'] = res['keywords_latest_revision']
                    this_row['earliest_revision'] = res['earliest_revision']
                    this_row['latest_revision'] = res['latest_revision']
                    metadata_data.append(this_row)
                    if len(metadata_data) >= n_lines_to_add:
                        smooth_bulk_insert(page_metadata, metadata_data)
                        metadata_data = []
                except Exception as e:
                    print(e)
                    print(keywords)
                    print('missing a field?>')
    if len(metadata_data) > 0:
        smooth_bulk_insert(page_metadata, metadata_data)

# #Creating the users table - current directory of users is hardcoded
def overwrite_users():
    session.query(users).delete()
    session.commit()
    data_to_add = []
    with open('users_in_table_user_data.txt','r') as userFile:
        for line in userFile:
            line_dict = {}
            res = json.loads(line)
            username = res['name']
            if len(username) > 0:
                if 'missing' in res.keys():
                    line_dict['user'] = username
                    line_dict['user_id'] = username
                    line_dict['edit_count'] = -1
                    line_dict['registration'] = "NA"
                elif 'invalid' in res.keys():
                    if ':' in username:
                        line_dict['user_id'] = '_'.join(map(str, res['name'].split(':')))
                    elif '.' in username:
                        # print('okay it is\n')
                        line_dict['user_id'] = '_'.join(map(str, res['name'].split('.')))
                    else:
                        print(f'An invalid user without a colon or period {res}')
                    line_dict['user'] = username
                    line_dict['edit_count'] = -1
                    line_dict['registration'] = "NA"
                else:
                    line_dict['user'] = username
                    line_dict['user_id'] = res['userid']
                    line_dict['edit_count'] = res['editcount']
                    line_dict['registration'] = res['registration']
            if len(line_dict.keys()) > 0:
                data_to_add.append(line_dict)
            if len(data_to_add) >= n_lines_to_add:
                smooth_bulk_insert(users, data_to_add)
                data_to_add = []
    if len(data_to_add) > 0:
        smooth_bulk_insert(users, data_to_add)

#Creating the page keywords table
def overwrite_page_keywords():
    session.query(page_keywords).delete()
    session.commit()
    filtered_data = []
    for keywords in os.listdir(directory + '/keyword_results'):
        if not is_in_skip_pages(keywords):
            with open(os.path.join(directory + '/keyword_results', keywords)) as keywordFile:
                keys = keywordFile.read()
                try:
                    res = json.loads(keys)
                    if not isinstance(res, dict):
                            print(f"Not a JSON object: {os.path.join(directory + '/keyword_results', keywords)}")
                except json.JSONDecodeError:
                    print(f"Invalid JSON: {os.path.join(directory + '/keyword_results', keywords)}")
                for item in res['revisions']:
                    revid = item['revid']
                    for word in item['keywords']:
                        for gen_word in word:
                            keyword_row = page_keywords(revid, gen_word, word[gen_word])
                            keyword_row = {'revision_id':revid, 'keyword': gen_word, 'count':word[gen_word]}
                            filtered_data.append(keyword_row)
                            if len(filtered_data) >= 50000:
                                smooth_bulk_insert(page_keywords, filtered_data)
                                filtered_data = []
    if len(filtered_data) > 0:
        smooth_bulk_insert(page_keywords, filtered_data)

def overwrite_sections():
    # total_time = time.time()
    inspector = inspect(engine)
    if 'sections' in inspector.get_table_names():
        sections.__table__.drop(engine)
    sections.__table__.create(engine)
    session.query(sections).delete()
    session.commit()
    revision_to_cat = dict()
    filtered_data = []
    for cat_name in os.listdir(directory + '/revision_contents_processed'):
        if '.txt' in cat_name and not is_in_skip_pages(cat_name):
            print(f'Processing {cat_name}')
        # if cat_name == 'Ashkenazi_Jews.txt.gz':
            with gzip.open(directory + '/revision_contents_processed/' + cat_name, 'rt') as file:
                # json_time = time.time()
                file = json.loads(file.read())
                # print(f'loading json took {time.time() - json_time:.4f}')
                for keys in file.keys():
                    # start_time = time.time()
                    parsed = wtp.parse(file[keys])
                    # parsed_time = time.time() - start_time
                    # print(f'Wikitextparser took {parsed_time:.4f} seconds')
                    sections_parsed = parsed.sections
                    # preloop_time = time.time()
                    for s in range(len(sections_parsed)):
                        to_add = {}
                        to_add['section_rank'] = s
                        to_add['keyword_ever_mentioned'] = False
                        to_add['revision_id'] = keys
                        to_add['section_title'] = str(sections_parsed[s].title).strip()
                        to_add['section_level'] = str(sections_parsed[s].level)
                        for term in genetics_terms:
                            if term in str(sections_parsed[s].plain_text).lower():
                                to_add['keyword_ever_mentioned'] = True
                                break
                        filtered_data.append(to_add)
                        if len(filtered_data) >= n_lines_to_add:
                            # before_bulk = time.time()
                            smooth_bulk_insert(sections, filtered_data)
                            filtered_data = []
                            # after_bulk = time.time() - before_bulk
                            # print(f'Bulk insert took {after_bulk:.4f} seconds')
                    # end_time = time.time() - preloop_time
                    # print(f'Looping through the sections took {end_time:.4f} seconds')
    if len(filtered_data) > 0:
        # leftover_bulk = time.time()
        smooth_bulk_insert(sections, filtered_data)
        # print(f'Leftover bulk took {time.time() - leftover_bulk:.4f} seconds')
    # print(f'Final time: {time.time() - total_time:.4f}')

if table == 'revision_histories':
    overwrite_revision_histories()
if table == 'users':
    overwrite_users()
if table == 'page_metadata':
    overwrite_page_metadata()
if table == 'page_keywords':
    overwrite_page_keywords()
if table == 'categories_revisions':
    overwrite_categories_revisions()
if table == 'create_user_list':
    grab_users_from_table(revision_histories)
if table == 'sections':
    overwrite_sections()



