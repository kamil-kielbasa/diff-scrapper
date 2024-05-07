import requests
import logging
import argparse
import os
import sys
import time
from datetime import datetime
import concurrent
import concurrent.futures.thread as futures


class Scraper:
    def __init__(self, args):
        self.group_id = args.group_id
        self.project_id = args.project_id

        self.private_token = {'PRIVATE-TOKEN': args.private_token}
        self.author_email = args.author_email
        self.since = args.since
        self.until = args.until
        self.base_url = args.base_url

        self.dir_name = ""
        self.request_retry_count = 3
        self.skip_archived_projects = True
        self.skip_empty_projects = True

        if args.verbose:
            logging.basicConfig(level=logging.INFO)
        else:
            logging.basicConfig(level=logging.ERROR)
        self.logger = logging.getLogger(__name__)

        self.subgroups_ids = []
        self.projects_id_name_dict = {}
        self.run()

    def run(self):
        self.create_output_folder()
        if self.group_id:
            self.logger.info('Processing subgroups')
            self.get_subgroups_recursive(self.group_id)
            self.logger.info('Getting projects')
            self.get_projects()
        else:
            self.logger.info('Getting single project')
            self.fetch_single_project()

        self.logger.info('Processing projects')
        self.process_projects()

    def create_output_folder(self):
        current_date = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
        self.dir_name = 'output_' + current_date
        os.mkdir(self.dir_name)
        self.logger.info('Created output folder: %s' % self.dir_name)

    def get_subgroups_recursive(self, group_id, level=0):
        names, ids = self.get_subgroups(group_id)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _name, _id in zip(names, ids):
                self.subgroups_ids.append(_id)
                self.logger.info('%s subgroup: %s = %s', '\t' * level, _name, _id)
                executor.submit(self.get_subgroups_recursive, _id, level + 1)

    def get_subgroups(self, group_id):
        url = f"{self.base_url}/groups/{group_id}/subgroups/"
        r = self.request(url)
        if r is None:
            return [], []
        else:
            data = r.json()
            names = [item['name'] for item in data]
            ids = [item['id'] for item in data]
            return names, ids

    def get_projects(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for _id_subgroup in self.subgroups_ids:
                executor.submit(self.fetch_projects, _id_subgroup)

    def fetch_projects(self, id_subgroup):
        url = f"{self.base_url}/groups/{id_subgroup}/projects"
        r = self.request(url)
        if r is None:
            self.logger.info("Skipping url: %s", url)
        projects = r.json()
        for project in projects:
            self.save_project_data(project)

    def fetch_single_project(self):
        url = f"{self.base_url}/projects/{self.project_id}"
        r = self.request(url)
        if r is None:
            self.logger.info("Skipping url: %s", url)
        self.save_project_data(r.json())

    def save_project_data(self, project):
        if (project['archived'] and self.skip_archived_projects) or (
                project['empty_repo'] and self.skip_empty_projects):
            self.logger.info("Skipping archived or empty project: %s", project['name'])
            return
        self.projects_id_name_dict[project['id']] = project['name']
        self.logger.info(" project name: %s = %s", project['name'], project['id'])

    def process_projects(self):
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(self.process_project, repo_id, repo_name) for repo_id, repo_name in
                       self.projects_id_name_dict.items()]

            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error("An error occurred during project processing: %s", e)

    def process_project(self, repo_id, repo_name):
        self.logger.info(f"Processing project: {repo_name} = {repo_id}")
        branches = self.get_branches(repo_id)
        commit_data = self.get_commits(repo_id, branches)
        self.save_diffs(commit_data, repo_id, repo_name)

    def get_branches(self, project_id):
        url = f"{self.base_url}/projects/{project_id}/repository/branches"
        r = self.request(url)
        if r is None:
            self.logger.warning("Failed to fetch branches for project URL %s", url)
            return []
        branches = [item['name'] for item in r.json()]
        return branches

    def get_commits(self, repository_id, branches):
        if len(branches) == 0:
            return {}

        commits_data = {}
        url = f"{self.base_url}/projects/{repository_id}/repository/commits"

        for branch in branches:
            payload = {'ref_name': branch, 'since': self.since, 'until': self.until}
            r = self.request(url, payload)
            if r is None:
                self.logger.warning("Failed to fetch commit data for project URL %s", url)
                return {}

            for item in r.json():
                commit_id = item['id']
                author_email = item['author_email']
                author_name = item['author_name']
                title = item['title']
                committed_date = item['committed_date']
                if author_email == self.author_email and commit_id not in commits_data:
                    commits_data[commit_id] = (author_name, author_email, committed_date, title)
        return commits_data

    def save_diffs(self, commit_data, repository_id, repo_name):
        if commit_data:
            path_diffs = self.create_file_path(repo_name)
            with open(path_diffs, 'w') as diff_file:
                for commit_hash, (author_name, author_email, committed_date, title) in commit_data.items():
                    url = self.base_url + f"/projects/{repository_id}/repository/commits/{commit_hash}/diff"
                    r = self.request(url)

                    diff_file.write(f'commit {commit_hash}\n')
                    diff_file.write(f'Author: {author_name} <{author_email}>\n')
                    date = datetime.strptime(committed_date.split('+')[0], '%Y-%m-%dT%H:%M:%S.%f')
                    diff_file.write(f"Date:   {date.strftime('%a %b %d %H:%M:%S %Y')} +{date.strftime('%f')[:4]}\n\n")
                    diff_file.write(f"    {title}\n\n")
                    for diff in r.json():
                        diff_file.write(f"+++ a/{diff['new_path']}\n")
                        diff_file.write(f"--- b/{diff['old_path']}\n")
                        diff_file.write(f"{diff['diff']}\n")

    def create_file_path(self, repo_name):
        file_name = repo_name.replace('/', '_').replace(' ', '') + '.patch'
        return os.path.join(self.dir_name, file_name)

    def request(self, url, params=None):
        retry_count = self.request_retry_count
        while retry_count > 0:
            try:
                r = requests.get(url, headers=self.private_token, params=params)
                if r.status_code == requests.codes.ok:
                    return r
                else:
                    self.logger.info(f"Request to {url} failed with status code: {r.status_code}. Retrying...")
            except requests.exceptions.RequestException as e:
                self.logger.info(f"Request to {url} failed: {e}. Retrying...")
            retry_count -= 1
            time.sleep(1)
        return None


def valid_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Invalid date format! Date must be in format YYYY-MM-DD."
        raise argparse.ArgumentTypeError(msg)


def parse_arguments():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='''
        Python web scrapper on GitLab API which allows to collect all changes from many repositories.

        1) First searching recursively for subgroups.
        2) Processing repositories from subgroup.
        3) As a result in the same directory:
           a) create directory with name: <output_YYYY-MM-DD-HH:MM:SS>
           b) diffs will be saved in files with names: <ProjectID.patch>
        ''',
        epilog='')

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-gid',
                       '--group_id',
                       help='The ID of the group.',
                       metavar='')
    group.add_argument('-pid',
                       '--project_id',
                       help='The ID of the project.',
                       metavar='')
    parser.add_argument('-pt',
                        '--private_token',
                        help='Private user access token on gitlab with scopes: api, read_api and read_repository.',
                        required=True,
                        metavar='')
    parser.add_argument('-ae',
                        '--author_email',
                        help='Author address email.',
                        required=True,
                        metavar='')
    parser.add_argument('-s',
                        '--since',
                        help='Only commits after or on this date are returned in format YYYY-MM-DD.',
                        required=True,
                        type=valid_date,
                        metavar='')
    parser.add_argument('-u',
                        '--until',
                        help='Only commits before or on this date are returned in format YYYY-MM-DD.',
                        required=True,
                        type=valid_date,
                        metavar='')
    parser.add_argument('-bu',
                        '--base_url',
                        help='Base URL to the project.',
                        default="https://sourcery.assaabloy.net/api/v4",
                        required=False,
                        metavar='')
    parser.add_argument('-v',
                        '--verbose',
                        help='Turn on logs during processing.',
                        required=False,
                        action='store_true')

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    return parser.parse_args()


def main():
    t = time.time()
    args = parse_arguments()
    Scraper(args)
    print(f"Total time: {time.time() - t}s")


if __name__ == '__main__':
    main()
