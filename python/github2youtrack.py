import re
import calendar
import time
import datetime
import sys
import csvClient
from csvClient.client import Client
import csvClient.youtrackMapping
from youtrackImporter import *

csvClient.FIELD_TYPES.update(youtrack.EXISTING_FIELD_TYPES)
from youtrack import YouTrackException, Issue, User, Comment
from youtrack.connection import Connection
from youtrack.importHelper import create_custom_field

import csv
import requests
import datetime

csvClient.FIELD_NAMES = {
    "Project Name"  :   "project_name",
    "Project Id"    :   "project_id",
    "Summary"       :   "summary",
    "State"         :   "State",
    "Id"            :   "numberInProject",
    "Created"       :   "created",
    "Updated"       :   "updated",
    "Assignee"      :   "Assignee",
    "Description"   :   "description",
    "Labels"        :   "Labels",
    "Author"        :   "reporterName"
}

csvClient.FIELD_TYPES = {
    "State"             :   "state[1]",
    "Assignee"          :   "user[1]",
    "Labels"            :   "enum[*]"
}

csvClient.DATE_FORMAT_STRING = "%Y-%m-%dT%H:%M:%SZ"

CSV_FILE = "github2youtrack.csv"

def main():
    github_user, github_password, github_repo, youtrack_url, youtrack_login, youtrack_password = sys.argv[1:8]
    github2csv(CSV_FILE, github_user, github_password, github_repo)
    csv2youtrack(CSV_FILE, youtrack_url, youtrack_login, youtrack_password)

def get_last_part_of_url(url_string):
    return url_string.split('/').pop()

# based on https://gist.github.com/unbracketed/3380407
def write_issues(r, csvout, repo):
    "output a list of issues to csv"
    if not r.status_code == 200:
        raise Exception(r.status_code)
    for issue in r.json():
        labels = []
        for label in issue['labels']:
            labels.append(label.get(u'name'))

        labels = '|'.join([str(x) for x in labels])

        assignee = issue['assignee']
        if assignee:
            assignee = assignee.get(u'login')
        else:
            assignee = ""

        created = issue['created_at']
        updated = issue['updated_at']

        author = get_last_part_of_url(issue['user'].get(u'url'))

        project = get_last_part_of_url(repo)

        csvout.writerow([project, project, issue['number'], issue['state'], issue['title'].encode('utf-8'), issue['body'].encode('utf-8'), created, updated, author, assignee, labels])

def github2csv(csvfile, github_user, github_password, github_repo):
    issues_url = 'https://api.github.com/repos/%s/issues' % github_repo
    AUTH = (github_user, github_password)

    r = requests.get(issues_url, auth=AUTH)
    csvout = csv.writer(open(csvfile, 'wb'))
    csvout.writerow(('Project Name', 'Project Id', 'Id', 'State', 'Summary', 'Description', 'Created', 'Updated', 'Author', 'Assignee', 'Labels'))
    write_issues(r, csvout, github_repo)

    #more pages? examine the 'link' header returned
    if 'link' in r.headers:
        pages = dict(
            [(rel[6:-1], url[url.index('<')+1:-1]) for url, rel in
                [link.split(';') for link in
                    r.headers['link'].split(',')]])
        while 'last' in pages and 'next' in pages:
            r = requests.get(pages['next'], auth=AUTH)
            write_issues(r, csvout, github_repo)
            if pages['next'] == pages['last']:
                break
# end of based code

def get_project(issue):
    for key, value in csvClient.FIELD_NAMES.items():
        if value == "project":
            return re.sub(r'\W+', "", issue[key])


def csv2youtrack(source_file, youtrack_url, youtrack_login, youtrack_password):
    target = Connection(youtrack_url, youtrack_login, youtrack_password)
    source = Client(source_file)

    config = CsvYouTrackImportConfig(csvClient.FIELD_NAMES, csvClient.FIELD_TYPES)
    importer = CsvYouTrackImporter(source, target, config)
    importer.import_csv()


class CsvYouTrackImporter(YouTrackImporter):
    def __init__(self, source, target, import_config):
        super(CsvYouTrackImporter, self).__init__(source, target, import_config)
        self._after = 0

    def import_csv(self, new_projects_owner_login=u'root'):
        projects = self._get_projects()
        self._source.reset()
        self.do_import(projects, new_projects_owner_login)

    def _to_yt_comment(self, comment):
        if isinstance(comment, str) or isinstance(comment, unicode):
            result = Comment()
            result.author = u'guest'
            result.text = comment
            result.created = str(int(time.time() * 1000))
            return result

    def get_field_value(self, field_name, field_type, value):
        if (field_name == self._import_config.get_project_name_key()) or (
        field_name == self._import_config.get_project_id_key()):
            return None
        if field_type == u'date':
            return self._import_config._to_unix_date(value)
        if (field_type.startswith('enum') and not isinstance(value, list)):
            return value.split('|')


        return super(CsvYouTrackImporter, self).get_field_value(field_name, field_type, value)

    def _to_yt_user(self, value):
        yt_user = User()
        yt_user.login = value.replace(' ', '_')
        yt_user.fullName = value
        yt_user.email = value
        return yt_user

    def _get_issue_id(self, issue):
        number_regex = re.compile("\d+")
        match_result = number_regex.search(issue[self._import_config.get_key_for_field_name(u'numberInProject')])
        return match_result.group()

    def _get_issues(self, project_id):
        issues = self._source.get_issues()
        for issue in issues:
            if self._import_config.get_project(issue)[0] == project_id:
                yield issue

    def _get_comments(self, issue):
        return issue[self._import_config.get_key_for_field_name(u'comments')]

    def _get_custom_field_names(self, project_ids):
        project_name_key = self._import_config.get_key_for_field_name(self._import_config.get_project_name_key())
        project_id_key = self._import_config.get_key_for_field_name(self._import_config.get_project_id_key())
        return [key for key in self._source.get_header() if (key not in [project_name_key, project_id_key])]

    def _get_projects(self):
        result = {}
        for issue in self._source.get_issues():
            project_id, project_name = self._import_config.get_project(issue)
            if project_id not in result:
                result[project_id] = project_name
        return result

    def _get_custom_fields_for_projects(self, project_ids):
        result = [elem for elem in [self._import_config.get_field_info(field_name) for field_name in
                                   self._get_custom_field_names(project_ids)] if elem is not None]
        return result


class CsvYouTrackImportConfig(YouTrackImportConfig):
    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(CsvYouTrackImportConfig, self).__init__(name_mapping, type_mapping, value_mapping)

    def _to_unix_date(self, date):
        if csvClient.DATE_FORMAT_STRING[-2:] == "%z":
            dt = datetime.datetime.strptime(date[:-6], csvClient.DATE_FORMAT_STRING[:-2].rstrip())
        else:
            dt = datetime.datetime.strptime(date, csvClient.DATE_FORMAT_STRING)
        return str(calendar.timegm(dt.timetuple()) * 1000)

    def get_project_id_key(self):
        return u'project_id'

    def get_project_name_key(self):
        return u'project_name'

    def get_project(self, issue):
        project_name_key = self.get_key_for_field_name(self.get_project_name_key())
        project_id_key = self.get_key_for_field_name(self.get_project_id_key())
        if project_name_key not in issue:
            print(u'ERROR: issue does not contain a project_name key called "%s"' % project_name_key)
            print(u'issue: ')
            print(issue)
            raise Exception("Bad csv file")
        if project_id_key not in issue:
            print(u'ERROR: issue does not contain a project_id key called "%s"' % project_id_key)
            print(u'issue: ')
            print(issue)
            raise Exception("Bad csv file")
        project_name = issue[project_name_key]
        project_id = issue.get(project_id_key, re.sub(r'\W+', "", project_name))
        return project_id, project_name

    def get_field_info(self, field_name):
        result = {AUTO_ATTACHED: self._get_default_auto_attached(),
                  NAME: field_name if field_name not in self._name_mapping else self._name_mapping[field_name],
                  TYPE: None}
        if result[NAME] in self._type_mapping:
            result[TYPE] = self._type_mapping[result[NAME]]
        elif result[NAME] in youtrack.EXISTING_FIELD_TYPES:
            result[TYPE] = youtrack.EXISTING_FIELD_TYPES[result[NAME]]
        result[POLICY] = self._get_default_bundle_policy()
        return result

if __name__ == "__main__":
    main()
