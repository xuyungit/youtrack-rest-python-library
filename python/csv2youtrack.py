import calendar
import re
import time
import datetime
import sys
import csvClient
from csvClient.client import Client
import csvClient.youtrackMapping
import youtrack
from youtrackImporter import YouTrackImporter, YouTrackImportConfig

csvClient.FIELD_TYPES.update(youtrack.EXISTING_FIELD_TYPES)
from youtrack import YouTrackException, Issue, User, Comment
from youtrack.connection import Connection
from youtrack.importHelper import create_custom_field


def main():
    source_file, target_url, target_login, target_password = sys.argv[1:5]
    csv2youtrack(source_file, target_url, target_login, target_password)

def get_project(issue):
    for key, value in csvClient.FIELD_NAMES.items():
        if value == "project":
            return re.sub(r'\W+', "", issue[key])

def csv2youtrack(source_file, target_url, target_login, target_password):
    target = Connection(target_url, target_login, target_password)
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
            result.authorLogin = u'guest'
            result.text = comment
            result.created = comment.created = str(int(time.time() * 1000))
            return result

    def _get_issue_id(self, issue):
        number_regex = re.compile("\d+")
        match_result = number_regex.search(issue[self._import_config.get_key_for_field_name(u'numberInProject')])
        return match_result.group()

    def _get_issues(self, project_ids, after, limit):
        if after < self._after:
            self._source.reset()
            self._after = 0
        result = []
        while True:
            issues = self._source.get_issue_list(limit - len(result))
            if not len(issues):
                return result
            for issue in issues:
                if self._import_config.get_project(issue)[0] in project_ids:
                    self._after += 1
                    if after <= self._after:
                        result.append(issue)
                if len(result) == limit:
                    break

        return result

    def _get_comments(self, issue):
        return issue[self._import_config.get_key_for_field_name(u'comments')]

    def _get_issue_tags(self, project_ids, after, limit):
        key = self._import_config.get_key_for_field_name(u'Tags')
        result = {}
        for issue in self._get_issues(project_ids, after, limit):
            if key in issue:
                result[self._get_issue_id(issue)] = issue[key]
        return result

    def _get_link_types(self):
        return []

    def _get_custom_field_names(self, project_ids):
        project_name_key = self._import_config.get_key_for_field_name(self._import_config.get_project_name_key())
        project_id_key = self._import_config.get_key_for_field_name(self._import_config.get_project_id_key())
        return [key for key in self._source.get_header() if (key not in [project_name_key, project_id_key])]

    def _get_projects(self):
        result = {}
        while True:
            issues = self._source.get_issue_list(200)
            if not len(issues):
                return result
            for issue in issues:
                project_id, project_name = self._import_config.get_project(issue)
                if project_id not in result:
                    result[project_id] = project_name

class CsvYouTrackImportConfig(YouTrackImportConfig):

    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(CsvYouTrackImportConfig, self).__init__(name_mapping, type_mapping, value_mapping)

    def _to_unix_date(self, date):
        if csvClient.DATE_FORMAT_STRING[-2:] == "%z":
            dt = datetime.datetime.strptime(date[:-6], csvClient.DATE_FORMAT_STRING[:-2])
        else:
            dt = datetime.datetime.strptime(date, csvClient.DATE_FORMAT_STRING)
        return str(calendar.timegm(dt.timetuple()) * 1000)

    def get_project_id_key(self):
        return u'project_name'

    def get_field_value(self, field_name, field_type, value):
        if (field_name == self.get_project_name_key()) or (field_name == self.get_project_id_key()):
            return None
        if field_type == u'date':
            return self._to_unix_date(value)
        return super(CsvYouTrackImportConfig, self).get_field_value(field_name, field_type, value)

    def get_project_name_key(self):
        return u'project_name'

    def _to_yt_user(self, value):
        yt_user = User()
        yt_user.login = value.replace(' ', '_')
        yt_user.fullName = value
        yt_user.email = value
        return yt_user

    def get_project(self, issue):
        project_name_key = self.get_key_for_field_name(self.get_project_name_key())
        project_id_key = self.get_key_for_field_name(self.get_project_id_key())
        project_name = issue[project_name_key]
        project_id = re.sub(r'[^A-Za-z0-9]+', "", issue[project_id_key])
        return project_id, project_name

if __name__ == "__main__":
    main()