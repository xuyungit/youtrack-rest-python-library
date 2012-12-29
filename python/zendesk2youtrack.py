import sys
from youtrack.connection import Connection
from youtrackImporter import YouTrackImporter, YouTrackImportConfig
from youtrackImporter import AUTO_ATTACHED, NAME, NUMBER_IN_PROJECT, TYPE, POLICY
from youtrack import User, Group
import zendesk
from zendesk.zendeskClient import ZendeskClient

__author__ = 'user'

def main():
    source_url, source_login, source_passowrd, target_url, target_login, target_password, project_id = sys.argv[1:8]
    zendesk2youtrack(source_url, source_login, source_passowrd, target_url, target_login, target_password, project_id)


def zendesk2youtrack(source_url, source_login, source_password, target_url, target_login, target_password, project_id):
    target = Connection(target_url, target_login, target_password)
    source = ZendeskClient(source_url, source_login, source_password)

    importer = ZendeskYouTrackImporter(source, target, ZendeskYouTrackImportConfig(zendesk.NAMES, {}, {}))
    importer.do_import({project_id : project_id})


class ZendeskYouTrackImporter(YouTrackImporter):
    def __init__(self, source, target, import_config):
        super(ZendeskYouTrackImporter, self).__init__(source, target, import_config)

    def _get_fields_with_values(self, project_id):
        return []

    def _to_yt_issue(self, issue, project_id):
        yt_issue = super(ZendeskYouTrackImporter, self)._to_yt_issue(issue, project_id)
        for key, value in issue[u'custom_fields']:
            self.process_field(key, project_id, yt_issue, value)
        return yt_issue

    def _to_yt_comment(self, comment):
        raise NotImplementedError

    def _get_attachments(self, param):
        return []

    def _get_issues(self, project_id, after, limit):
        return self._source.get_issues(after, limit)

    def _get_comments(self, issue):
        return []

    def _get_custom_fields_for_projects(self, project_ids):
        fields = self._source.get_custom_fields()
        result = []
        for field in fields:
            yt_field = {NAME: self._import_config.get_field_name(field[u'title'])}
            yt_field[AUTO_ATTACHED] = True
            yt_field[TYPE] = self._import_config.get_field_type(yt_field[NAME], field[u'type'])
            if yt_field[TYPE] is not None:
                result.append(yt_field)
        return result

    def _get_issue_links(self, project_id, after, limit):
        return []

    def _to_yt_user(self, value):
        user = self._source.get_user(value)
        yt_groups = []
        for g in self._source.get_groups_for_user(value):
            ytg = Group()
            ytg.name = g
            yt_groups.append(ytg)
        yt_user = User()
        yt_user.login = user[u'email']
        yt_user.email = user[u'email']
        yt_user.fullName = user[u'name']
        yt_user.getGroups = lambda: yt_groups
        return yt_user


class ZendeskYouTrackImportConfig(YouTrackImportConfig):
    def __init__(self, name_mapping, type_mapping, value_mapping=None):
        super(ZendeskYouTrackImportConfig, self).__init__(name_mapping, type_mapping, value_mapping)

    def get_predefined_fields(self):
        return [
            {NAME: u'Type', TYPE: u'enum[1]', POLICY: '0'},
            {NAME: u'Priority', TYPE: u'enum[1]', POLICY: '0'},
            {NAME: u'State', TYPE: u'state[1]', POLICY: '0'},
            {NAME: u'Assignee', TYPE: u'user[1]', POLICY: '2'},
            {NAME: u'Due date', TYPE: u'date'},
            {NAME: u'Organization', TYPE: u'enum[1]', POLICY:'0'}
        ]

    def get_field_type(self, name, type):
        {}.get(type)


if __name__ == "__main__":
    main()