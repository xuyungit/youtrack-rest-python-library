import calendar
import sys
import datetime
import urllib
import urllib2
import jira
from jira.client import JiraClient
from youtrack import Issue, YouTrackException, Comment, Link
import youtrack
from youtrack.connection import Connection
from youtrack.importHelper import create_bundle_safe

jt_fields = []

def main():
    source_url, source_login, source_password, target_url, target_login, target_password, project_id, issues_count = sys.argv[1:9]
    issues_count = int(issues_count)
    skip_count = int(sys.argv[9]) if len(sys.argv) > 9 else 0
    if issues_count < 1:
        raise ValueError('Issues count cannot be negative or zero!')
    if skip_count < 0:
        raise ValueError('Skip count cannot be negative!')
    if skip_count >= issues_count:
        raise ValueError('Skip count should be less then issues count!')

    jira2youtrack(source_url, source_login, source_password, target_url, target_login, target_password, project_id,
        issues_count, skip_count)


def create_yt_issue_from_jira_issue(target, issue, project_id):
    yt_issue = Issue()
    yt_issue['comments'] = []
    yt_issue.numberInProject = issue['key'][(issue['key'].find('-') + 1):]
    for field, value in issue['fields'].items():
        if value is None:
            continue
        field_name = get_yt_field_name(field)
        field_type = get_yt_field_type(field_name)
        if field_name == 'comment':
            for comment in value['comments']:
                yt_comment = Comment()
                yt_comment.text = comment['body']
                comment_author_name = "guest"
                if 'author' in comment:
                    comment_author = comment['author']
                    create_user(target, comment_author)
                    comment_author_name = comment_author['name']
                yt_comment.author = comment_author_name.replace(' ', '_')
                yt_comment.created = to_unix_date(comment['created'])
                yt_comment.updated = to_unix_date(comment['updated'])
                yt_issue['comments'].append(yt_comment)

        elif (field_name is not None) and (field_type is not None):
            if isinstance(value, list) and len(value):
                yt_issue[field_name] = []
                for v in value:
                    create_value(target, v, field_name, field_type, project_id)
                    yt_issue[field_name].append(get_value_presentation(field_type, v))
            else:
                if isinstance(value, int):
                    value = str(value)
                if len(value):
                    create_value(target, value, field_name, field_type, project_id)
                    yt_issue[field_name] = get_value_presentation(field_type, value)
        else:
            print field_name
    return yt_issue


def process_labels(target, issue):
    tags = issue['fields']['labels']
    for tag in tags:
    #        tag = tag.replace(' ', '_')
    #        tag = tag.replace('-', '_')
        try:
            target.executeCommand(issue['key'], 'tag ' + tag)
        except YouTrackException:
            try:
                target.executeCommand(issue['key'], ' tag ' + tag.replace(' ', '_').replace('-', '_'))
            except YouTrackException, e:
                print(str(e))


def get_yt_field_name(jira_name):
    if jira_name in jira.FIELD_NAMES:
        return jira.FIELD_NAMES[jira_name]
    return jira_name


def get_yt_field_type(yt_name):
    result = jira.FIELD_TYPES.get(yt_name)
    if result is None:
        result = youtrack.EXISTING_FIELD_TYPES.get(yt_name)
    return result


def process_links(target, issue, yt_links):
    for sub_task in issue['fields']['subtasks']:
        parent = issue[u'key']
        child = sub_task[u'key']
        link = Link()
        link.typeName = u'subtask'
        link.source = parent
        link.target = child
        yt_links.append(link)

    links = issue['fields'][u'issuelinks']
    for link in links:
        if u'inwardIssue' in link:
            source_issue = issue[u'key']
            target_issue = link[u'inwardIssue'][u'key']
        elif u'outwardIssue' in link:
            source_issue = issue[u'key']
            target_issue = link[u'outwardIssue'][u'key']
        else:
            continue

        type = link[u'type']
        type_name = type[u'name']
        inward = type[u'inward']
        outward = type[u'outward']
        try:
            if inward == outward:
                target.createIssueLinkTypeDetailed(type_name, outward, inward, False)
            else:
                target.createIssueLinkTypeDetailed(type_name, outward, inward, True)
        except YouTrackException:
            pass

        yt_link = Link()
        yt_link.typeName = type_name
        yt_link.source = source_issue
        yt_link.target = target_issue
        yt_links.append(yt_link)


def create_user(target, value):
    try:
        target.createUserDetailed(value['name'].replace(' ', '_'), value['displayName'], value[u'name'], 'fake_jabber')
    except YouTrackException, e:
        print(str(e))


def create_value(target, value, field_name, field_type, project_id):
    if field_type.startswith('user'):
        create_user(target, value)
        value['name'] = value['name'].replace(' ', '_')
    if field_name in jira.EXISTING_FIELDS:
        return
    if field_name.lower() not in [field.name.lower() for field in target.getProjectCustomFields(project_id)]:
        if field_name.lower() not in [field.name.lower() for field in target.getCustomFields()]:
            target.createCustomFieldDetailed(field_name, field_type, False, True, False, {})
        if field_type in ['string', 'date', 'integer']:
            target.createProjectCustomFieldDetailed(project_id, field_name, "No " + field_name)
        else:
            bundle_name = field_name + " bundle"
            create_bundle_safe(target, bundle_name, field_type)
            target.createProjectCustomFieldDetailed(project_id, field_name, "No " + field_name, {'bundle': bundle_name})
    if field_type in ['string', 'date', 'integer']:
        return
    project_field = target.getProjectCustomField(project_id, field_name)
    bundle = target.getBundle(field_type, project_field.bundle)
    try:
        if 'name' in value:
            target.addValueToBundle(bundle, value['name'])
        elif 'value' in value:
            target.addValueToBundle(bundle, value['value'])
    except YouTrackException:
        pass


def to_unix_date(time_string):
    if len(time_string) == 10:
        #just date
        dt = datetime.datetime.strptime(time_string, '%Y-%m-%d')
        tz_diff = 0
    else:
        time = time_string[:time_string.rfind('.')].replace('T', ' ')
        time_zone = time_string[-5:]
        tz_diff = 1
        if time_zone[0] == '-':
            tz_diff = -1
        tz_diff *= (int(time_zone[1:3]) * 60 + int(time_zone[3:5]))
        dt = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
    return str((calendar.timegm(dt.timetuple()) + tz_diff) * 1000)


def get_value_presentation(field_type, value):
    if field_type == 'date':
        return to_unix_date(value)
    if field_type == 'integer':
        return str(value)
    if field_type == 'string':
        return value
    if 'name' in value:
        return value['name']
    if 'value' in value:
        return value['value']


def process_attachments(source, target, issue):
    for attach in issue['fields']['attachment']:
        attachment = JiraAttachment(attach, source)
        if 'author' in attach:
            create_user(target, attach['author'])
        target.createAttachmentFromAttachment(issue['key'], attachment)


def jira2youtrack(source_url, source_login, source_password, target_url, target_login, target_password, project_id,
                  issues_count, skip_count):
    print("source_url      : " + source_url)
    print("source_login    : " + source_login)
    print("target_url      : " + target_url)
    print("target_login    : " + target_login)
    print("project_id      : " + project_id)
    print("issues_count    : ", issues_count)
    print("skip_count      : ", skip_count)

    first_chunk = skip_count / 10
    last_chunk = issues_count / 10
    if issues_count % 10:
        last_chunk += 1

    source = JiraClient(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)

    try:
        target.createProjectDetailed(project_id, project_id, "", target_login)
    except YouTrackException:
        pass

    for i in range(first_chunk, last_chunk):
        start = i * 10
        end = (i + 1) * 10
        if start < skip_count: start = skip_count
        if end > issues_count: end = issues_count
        try:
            jira_issues = source.get_issues(project_id, start, end)
            target.importIssues(project_id, project_id + " assignees",
                [create_yt_issue_from_jira_issue(target, issue, project_id) for issue in
                 jira_issues])
            for issue in jira_issues:
                process_labels(target, issue)
                process_attachments(source, target, issue)
        except YouTrackException, e:
            print(str(e))

    for i in range(first_chunk, last_chunk):
        start = i * 10
        end = (i + 1) * 10
        if start < skip_count: start = skip_count
        if end > issues_count: end = issues_count
        jira_issues = source.get_issues(project_id, start, end)
        links = []
        for issue in jira_issues:
            process_links(target, issue, links)
        target.importLinks(links)

class JiraAttachment(object):
    def __init__(self, attach, source):
        self.authorLogin = attach['author']['name'].replace(' ', '_') if 'author' in attach else 'root'
        self._url = attach['content']
        self.name = attach['filename']
        self.created = to_unix_date(attach['created'])
        self._source = source

    def getContent(self):
        return urllib2.urlopen(urllib2.Request(self._url, headers=self._source._headers))

if __name__ == '__main__':
    main()

