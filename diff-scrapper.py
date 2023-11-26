import requests
import http
import argparse
import os
import time
import multiprocessing
from datetime import datetime
from time import gmtime, strftime
from pytz import timezone

GROUPS = 'groups/'
SUBGROUPS = 'subgroups/'
PROJECT = 'projects/'
BRANCHES = 'branches/'
REPOSITORY = 'repository/'
COMMITS = 'commits/'
DIFF = 'diff/'

CEND      = '\33[0m'
CBOLD     = '\33[1m'
CITALIC   = '\33[3m'
CURL      = '\33[4m'
CBLINK    = '\33[5m'
CBLINK2   = '\33[6m'
CSELECTED = '\33[7m'

CBLACK  = '\33[30m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'
CVIOLET = '\33[35m'
CBEIGE  = '\33[36m'
CWHITE  = '\33[37m'


def get_subgroups(base_url, group_id, private_token):
    ids = []
    names = []
    r = requests.get(base_url + GROUPS + group_id + '/' + SUBGROUPS, headers=private_token)
    if r.status_code == http.HTTPStatus.OK:
        for item in r.json():
            ids.append(item['id'])
            names.append(item['name'])
    return (names, ids)


def get_repositories(base_url, subgroup_id, private_token):
    ids = []
    names = []
    r = requests.get(base_url + GROUPS + subgroup_id + '/', headers=private_token)
    if r.status_code == http.HTTPStatus.OK:
        for i in range(len(r.json()['projects'])):
            ids.append(r.json()['projects'][i]['id'])
            names.append(r.json()['projects'][i]['name'])
    return (names, ids)


def get_branches_from_repository(base_url, repository_id, author_email, private_token):
    branches = []
    r = requests.get(base_url + PROJECT + repository_id + '/' + REPOSITORY + BRANCHES, headers=private_token)
    if r.status_code == http.HTTPStatus.OK:
        for item in r.json():
            if item['commit']['author_email'] == author_email:
                branches.append(item['name'])
    return branches


def get_commits_info(base_url, repository_id, branch_name, _author_name, since_date, until_date, private_token):
    hashes = []
    author_name = []
    author_email = []
    committed_date = []
    title = []
    payload = {'ref_name': branch_name, 'author': _author_name, 'since': since_date + 'T00:00:00.000+00:00', 'until': until_date + 'T23:59:59.999+00:00'}
    r = requests.get(base_url + PROJECT + repository_id + '/' + REPOSITORY + COMMITS, headers=private_token, params=payload)
    if r.status_code == http.HTTPStatus.OK:
        hashes = []
        author_name = []
        author_email = []
        committed_date = []
        title = []
        for item in r.json():
            hashes.append(item['id'])
            author_name.append(item['author_name'])
            author_email.append(item['author_email'])
            committed_date.append(item['committed_date'])
            title.append(item['title'])
    return (hashes, author_name, author_email, committed_date, title)


def save_diffs_to_file(base_url, hashes, author_name, author_email, committed_date, title, repository_id, private_token, file_name):
    with open(file_name, 'w') as log:
        for i in range(len(hashes)):
            r = requests.get(base_url + PROJECT + repository_id + '/' + REPOSITORY + COMMITS + hashes[i] + '/' + DIFF, headers=private_token)
            if r.status_code == http.HTTPStatus.OK:
                log.write('commit ' + hashes[i] + '\n')
                log.write('Author: ' + author_name[i] + ' <' + author_email[i] + '>\n')
                date = datetime.strptime(committed_date[i].split('+')[0], '%Y-%m-%dT%H:%M:%S.%f')
                month_name = date.strftime('%A')
                day_name = date.strftime('%B')
                day_number = date.strftime('%d')
                hour_number = date.strftime('%H')
                minute_number = date.strftime('%M')
                second_number = date.strftime('%s')
                year_number = date.strftime('%Y')
                miliseconds_number = date.strftime('%f')
                log.write('Date:   ' + month_name[:3] + ' ' + day_name[:3] + ' ' + str(int(day_number)) + ' ' + hour_number + ':' + minute_number + ':' + second_number[:2] + ' ' + year_number + ' +' + miliseconds_number[:4] + '\n')
                log.write('\n')
                log.write('    ' + title[i] + '\n')
                log.write('\n')
                for j in range(len(r.json())):
                    log.write('+++ a/' + r.json()[j]['new_path'] + '\n')
                    log.write('--- b/' + r.json()[j]['old_path'] + '\n')
                    log.write(r.json()[j]['diff'] + '\n')


def process_subgroup(base_url, id, args, dir_name, prefix, verboseprint):
    repo_names, repo_ids = get_repositories(base_url, str(base_ids[i]), private_token)
    for j in range(len(repo_ids)):
        verboseprint(CGREEN + 'repository:' + CEND, repo_names[j], '=', repo_ids[j])
        branches = get_branches_from_repository(base_url, str(repo_ids[j]), args.author_email, private_token)
        for k in range(len(branches)):
            verboseprint('\t', CBLUE + 'branch:' + CEND, branches[k])
            hashes, auth_name, auth_email, committed_date, title = get_commits_info(base_url, str(repo_ids[j]), branches[k], args.author_name, args.since, args.until, private_token)
            for z in range(len(hashes)):
                verboseprint('\t\t', CYELLOW + 'hashes:' + CEND, hashes[z])
            if len(hashes) > 0:
                filename = prefix + '__' + repo_names[j].replace('/', '_').replace(' ', '') + '___' + branches[k].replace('/', '_').replace(' ', '') + '___' + '.patch'
                verboseprint('\t\t\t', CRED + 'file:' + CEND, dir_name + '/' + filename)
                save_diffs_to_file(base_url, hashes, auth_name, auth_email, committed_date, title, str(repo_ids[j]), private_token, dir_name + '/' + filename)


if __name__ == '__main__':
    start = time.time()

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description=
        '''
        Python web scrapper on GitLab API which allows to collect all changes from many repositories.

        1) First searching recursively for subgroups.
        2) Processing repositories from subgroup.
        3) As a result in the same directory:
           a) create directory with name: <output_YYYY-MM-DD-HH:MM:SS>
           b) diffs will be saved in files with names: <YYYY-MM__repository_name__branch_name.patch>
        ''',
        epilog='')

    parser.add_argument('-bu',
                        '--base_url',
                        help='Base URL to the project.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-gid',
                        '--group_id',
                        help='The ID of the project owned by the authenticated user.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-pt',
                        '--private_token',
                        help='Private user access token on gitlab with scopes: api, read_api and read_repository.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-an',
                        '--author_name',
                        help='Author name in following pattern: <Surname, Firstname>.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-ae',
                        '--author_email',
                        help='Author address email.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-s',
                        '--since',
                        help='Only commits after or on this date are returned in format <YYYY-MM-DD>.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-u',
                        '--until',
                        help='Only commits before or on this date are returned in format <YYYY-MM-DD>.',
                        action='store',
                        type=str,
                        required=True,
                        metavar='')
    parser.add_argument('-v',
                        '--verbose',
                        help='With value \'True\' turn on additional logs during processing.',
                        type=str,
                        required=False,
                        metavar='')

    args = parser.parse_args()

    verboseprint = print if args.verbose == 'True' else lambda *a, **k: None

    base_url = args.base_url

    now_utc = datetime.now(timezone('UTC'))
    now_europe = now_utc.astimezone(timezone('Europe/Warsaw'))
    curr_time = now_europe.strftime('%Y-%m-%d-%H:%M:%S')
    dir_name = 'output_' + curr_time
    os.mkdir(dir_name)

    private_token = {'PRIVATE-TOKEN': args.private_token}

    base_names = []
    base_ids = []

    base_names.append('ASSA ABLOY Device Configuration Protocol')
    base_ids.append('524')

    names, ids = get_subgroups(base_url, args.group_id, private_token)
    for i in range(len(ids)):
        verboseprint(CBEIGE + 'subgroup:' + CEND, names[i], '=', ids[i])
        base_ids.append(ids[i])
        base_names.append(names[i])
        names2, ids2 = get_subgroups(base_url, str(ids[i]), private_token)
        for j in range(len(ids2)):
            verboseprint('\t', CBEIGE + 'subgroup:' + CEND, names2[j], '=', ids2[j])
            base_ids.append(ids2[j])
            base_names.append(names2[j])
            names3, ids3 = get_subgroups(base_url, str(ids2[j]), private_token)
            for k in range(len(ids3)):
                verboseprint('\t\t', CBEIGE + 'subgroup:' + CEND, names3[k], '=', ids3[k])

    verboseprint('\n\n')

    processes_list = []
    for i in range(len(base_ids)):
        processes_list.append(multiprocessing.Process(target=process_subgroup, args=(base_url, str(base_ids[i]), args, dir_name, curr_time[:7], verboseprint)))
    for i in range(len(processes_list)):
        processes_list[i].start()
    for i in range(len(processes_list)):
        processes_list[i].join()

    end = time.time()
    print('\n', end - start, '[s]')