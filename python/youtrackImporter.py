from youtrack import YouTrackException, Issue
import youtrack
from youtrack.connection import Connection
from youtrack.importHelper import create_custom_field

__author__ = 'user'

name = u'name'
type = u'type'
policy = u'bundle_policy'
auto_attached = u'auto_attached'

class YouTrackImporter(object):

    def __init__(self, source, target, import_config):
        self._source = source
        self._target = target
        self._import_config = import_config

    def do_import(self, projects, new_projects_owner_login=u'root'):
        project_ids = projects.keys()
        self._create_auto_attached_fields()
        self._create_custom_fields(project_ids)
        for project_id, project_name in projects.items():
            self._create_project(project_id, project_name, new_projects_owner_login)
            self._attach_fields_to_project(project_id)
            self._add_value_to_fields_in_project(project_id)
            self._import_issues(project_id)
        self._import_tags(project_ids)
        self._import_issue_link_types()
        self._import_issue_links(project_ids)

    def _create_auto_attached_fields(self):
        predefined_fields = self._import_config.get_predefined_fields()
        for field in predefined_fields:
            self._create_field(field[name], field[type], field.get(policy))

    def _create_field(self, field_name, field_type, attach_bundle_policy, auto_attached=True):
        create_custom_field(self._target, field_type, field_name, auto_attached, bundle_policy=attach_bundle_policy)

    def _create_custom_fields(self, project_ids):
        custom_fields = self._source._get_custom_fields(project_ids)
        for field in custom_fields:
            yt_field = self._import_config.get_field_info(field)
            if yt_field is not None:
                self._create_field(yt_field[name], yt_field[type], yt_field.get(policy), yt_field[auto_attached])

    def _create_project(self, project_id, project_name, project_lead_login):
        try:
            self._target.getProject(project_id)
        except YouTrackException:
            self._target.createProjectDetailed(project_id, project_name, u'', project_lead_login)

    def _attach_fields_to_project(self, project_id):
        project_fields = self._get_custom_fields(project_id)
        for field in project_fields:
            yt_field = self._import_config.get_field_info(field)
            if  (yt_field is not None) and (not yt_field[u'auto_attached']):
                # this means, that field was not attached to project yet
                field_name = yt_field[name]
                try:
                    self._target.createProjectCustomFieldDetailed(project_id, field_name, u'No ' + field_name)
                except YouTrackException:
                    print(u'Field [%s] is already attached' % field_name)

    def _import_issues(self, project_id):
        after = 0
        limit = 100
        while True:
            issues = self.get_issues([project_id], after, limit)
            self._target.importIssues(project_id, project_id + u' assignees',
                [self._to_yt_issue(issue, project_id) for issue in issues])
            for issue in issues:
                issue_id = self._get_issue_id(issue)
                issue_attachments = self._get_attachments(issue_id)
                yt_issue_id = u'%s-%s' % (project_id, issue_id)
                self._import_attachments(issue_id, issue_attachments)

    def _import_tags(self, project_ids):
        after = 0
        limit = 200
        existing_tags = set([])
        while True:
            issue_tags = self.get_issue_tags(project_ids, after, limit).values()
            if not len(issue_tags):
                break
            existing_tags |= set(issue_tags)

    def _is_prefix_of_any_other_tag(self, tag, other_tags):
        for t in other_tags:
            if t.startswith(tag) and (t != tag):
                return True
        return False


    def _import_tags(self, source, target, project_ids, collected_tags):
        tags_to_import_now = set([])
        tags_to_import_after = set([])
        for tag in collected_tags:
            if self._is_prefix_of_any_other_tag(tag, collected_tags):
                tags_to_import_after.add(tag)
            else:
                tags_to_import_now.add(tag)
        max = 100
        for project_id in project_ids:
            after = 0
            while True:
                issue_tags = self.get_issue_tags(project_id, after, max)
                if not len(issue_tags):
                    break
                for (issue_id, tags) in issue_tags.items():
                    yt_issue_id = u'%s-%s' % (project_id, issue_id)
                    for tag in tags:
                        if tag in tags_to_import_now:
                            try:
                                target.executeCommand(yt_issue_id, u'tag ' + tag)
                            except YouTrackException:
                                print(u'Failed to import tag for issue [%s]' % yt_issue_id)
                after += max
        if len(tags_to_import_after):
            self._import_tags(source, target, project_ids, tags_to_import_after)

    def _import_issue_links(self, project_ids):
        after = 0
        limit = 100
        while True:
            links = self._get_issue_links(project_ids, after, limit)
            if not len(links):
                break
            self._target.importLinks([self.to_yt_link(lnk) for lnk in links])
            after += limit

    def _import_issue_link_types(self):
        for type in self._get_link_types():
            yt_type = self._import_config.get_link_type(type)
            try:
                self._target.createIssueLinkType(yt_type)
            except:
                print(u'Issue link type [%s] already exist' % yt_type.name)

    def _get_link_types(self):
        raise NotImplementedError

    def _get_custom_fields(self, project_id):
        raise NotImplementedError

    def _get_issue_links(self, project_ids, after, limit):
        raise NotImplementedError

    def _to_yt_issue(self, issue, project_id):
        result = Issue()
        result.comments = [self.to_yt_comment(comment) for comment in self._get_comments(issue)]
        for (key, value) in issue:
            # we do not need fields with empty values
            if value is None:
                continue
            if isinstance(value, list) and not len(value):
                continue

            #get yt field name and field type
            field_name = self._get_field_name(key, project_id)
            if field_name is None:
                continue
            field_type = self._get_field_type(field_name)
            if (field_type is None) and (field_name not in youtrack.EXISTING_FIELDS):
                continue

            value = self._import_config.get_field_value(field_name, value)
            if isinstance(value.list):
                for v in value:
                    self._add_value_to_field(project_id, field_name, field_type, v)
            else:
                self._add_value_to_field(project_id, field_name, field_type, value)

            if (field_type is not None) and field_type.startswith(u'user'):
                if isinstance(value, list):
                    value = [v.login for v in value]
                else:
                    value = value.login
            if not isinstance(value, list):
                value = unicode(value)
            result[field_name] = value
        return result

    def _get_field_name(self, field_name, project_id):
        field = self._import_config.get_field_info(field_name)
        if field is not None:
            field_name = field[name]
        if field_name in youtrack.EXISTING_FIELDS:
            return field_name
        try:
            self._target.getProjectCustomField(project_id, field_name)
            return field_name
        except YouTrackException:
            return None

    def _get_field_type(self, field_name):
        if field_name in youtrack.EXISTING_FIELD_TYPES:
            return youtrack.EXISTING_FIELD_TYPES[field_name]
        try:
            return self._target.getCustomField(field_name).type
        except YouTrackException:
            return None

    def _add_value_to_field(self, project_id, field_name, field_type, value):
        if (field_type is not None) and field_type.startswith(u'user'):
            self._target.importUsers([value])
            value = value.login
        if field_name in youtrack.EXISTING_FIELDS:
            return
        custom_field = self._target.getProjectCustomField(project_id, field_name)
        if hasattr(custom_field, u'bundle'):
            bundle = self._target.getBundle(field_type, custom_field.bundle)
            try:
                self._target.addValueToBundle(bundle, value)
            except YouTrackException:
                pass

    def _add_value_to_fields_in_project(self, project_id):
        for field in self._get_fields_with_values(project_id):
            field_name = self._get_field_name(field[name], project_id)
            pcf = self._target.getProjectCustomField(project_id, field_name)
            if hasattr(pcf, u'bundle'):
                field_type = pcf.type[0:-3]
                bundle = self._target.getBundle(field_type, pcf.bundle)
                yt_values = [v for v in [field[u'converter'](value, bundle,
                    lambda name, value_name: self._import_config.get_field_value(name, value_name)) for value in
                                         field[u'values']] if len(v)]

    def _get_fields_with_values(self, project_id):
        return []

    def to_yt_comment(self, comment):
        raise NotImplementedError

    def to_yt_link(self, link):
        raise NotImplementedError

    def _get_issue_id(self, issue):
        raise NotImplementedError

    def _get_attachments(self, param):
        raise NotImplementedError

    def get_issues(self, project_ids, after, limit):
        raise NotImplementedError

    def _import_attachments(self, issue_id, issue_attachments):
        raise NotImplementedError

    def _get_comments(self, issue):
        raise NotImplementedError

    def get_issue_tags(self, project_ids, after, limit):
        raise NotImplementedError

class YouTrackImportConfig(object):

    def __init__(self, name_mapping, type_mapping, value_mapping=None, link_type_mapping=None):
        self._name_mapping = name_mapping
        self._type_mapping = type_mapping
        self._value_mapping = value_mapping if value_mapping is not None else {}
        self._link_type_mapping = link_type_mapping if link_type_mapping is not None else {}

    def get_field_value(self, field_name, field_type, value):
        if value is None:
            return None
        values_map = self._value_mapping[field_name] if field_name in self._value_mapping else {}
        if isinstance(value, str) or isinstance(value, unicode):
            return values_map[value] if value in values_map else value.replace("/", " ")
        if isinstance(value, int):
            return values_map[value] if value in values_map else str(value)
        if field_type.startswith(u'user'):
            return self._to_yt_user(value)
        if isinstance(value, list):
            return [self.get_field_value(field_name, field_type, v) for v in value]

    def _get_default_auto_attached(self):
        return True

    def _get_default_bundle_policy(self):
        return 0

    def get_field_info(self, field_name):
        result = {auto_attached : self._get_default_auto_attached()}
        result[name] = field_name if field_name not in self._name_mapping else self._name_mapping[field_name]
        result[type] = None
        if result[name] in self._type_mapping:
            result[type] = self._type_mapping[result[name]]
        elif result[name] in youtrack.EXISTING_FIELD_TYPES:
            result[type] = youtrack.EXISTING_FIELD_TYPES[result[name]]
        result[policy] = self._get_default_bundle_policy()
        return result

    def get_predefined_fields(self):
        return []

    def get_link_type(self, type):
        return self._link_type_mapping[type] if type in self._link_type_mapping else type

    def _to_yt_user(self, value):
        raise NotImplementedError



