#! /usr/bin/env python

import sys
import re
import requests
import time
import csv
import csvClient
import csv2youtrack
from youtrack.importHelper import utf8encode

csvClient.FIELD_NAMES = {
    "Project Name": "project_name",
    "Project Id": "project_id",
    "Summary": "summary",
    "State": "State",
    "Id": "numberInProject",
    "Created": "created",
    "Updated": "updated",
    "Resolved": "resolved",
    "Assignee": "Assignee",
    "Description": "description",
    "Labels": "Labels",
    "Author": "reporterName",
    "Milestone": "Fix versions"
}

csvClient.FIELD_TYPES = {
    "State": "state[1]",
    "Assignee": "user[1]",
    "Labels": "enum[*]",
    "Fix versions": "version[*]",
    "Type": "enum[1]"
}

csvClient.DATE_FORMAT_STRING = "%Y-%m-%dT%H:%M:%SZ"
csvClient.VALUE_DELIMITER = "|"

CSV_FILE = sys.argv[0].replace('.py', '') + "-{repo}-{data}.csv"

AUTH = None


def main():
    global AUTH

    (github_user, github_password, github_repo,
     youtrack_url, youtrack_login, youtrack_password) = sys.argv[1:8]

    AUTH = (github_user, github_password)

    if github_repo.find('/') > -1:
        github_repo_owner, github_repo = github_repo.split('/')
        github_repo = github_repo.replace('/', '_')
    else:
        github_repo_owner = github_user
    issues_csv_file = CSV_FILE.format(repo=github_repo, data='issues')
    comments_csv_file = CSV_FILE.format(repo=github_repo, data='comments')
    attachments_csv_file = CSV_FILE.format(repo=github_repo, data='attachments')

    github2csv(
        issues_csv_file,
        comments_csv_file,
        attachments_csv_file,
        github_repo,
        github_repo_owner)
    csv2youtrack.csv2youtrack(
        issues_csv_file,
        youtrack_url,
        youtrack_login,
        youtrack_password,
        comments_csv_file,
        attachments_csv_file)


def get_last_part_of_url(url_string):
    return url_string.split('/').pop()


def req_get(url):
    r = requests.get(url, auth=AUTH)
    attempts = 10
    while r.status_code != 200 and attempts:
        time.sleep(int(300/attempts))
        r = requests.get(url, auth=AUTH)
        attempts -= 1
    if r.status_code != 200:
        raise Exception('%d: %s' % (r.status_code, r.request.url))
    return r


def get_user_info(user):
    login = ''
    fullname = ''
    email = ''
    if 'url' in user:
        try:
            r = req_get(user['url'])
            _user = r.json()
            login = _user['login']
            fullname = _user.get('name') or ''
            email = _user.get('email') or ''  # GitHub can return null (None)
        except Exception, e:
            print 'Cannot get user info', e.message
    if not login:
        login = user.get('login') or 'guest'
    if fullname or email:
        return ';'.join((login, fullname, email))
    return login


def process_attachments(content):
    links = re.findall(r'!\[([^]]+?)\]\(([^)]+?)\)', content)
    # Convert image attachments Draw Picture wiki: !image.png!
    content = re.sub(r'!\[([^]]+?)\]\([^)]+?\)', r'!\1!', content)
    # Convert markdown links to wiki
    content = re.sub(r'!?\[([^]]*?)\]\(([^)]+?)\)', r'[\2 \1]', content)
    return content, links


def convert_code_blocks(content):
    # Convert only one-line code blocks
    # because multi-line blocks are supported by YouTrack
    return re.sub(r'```(.+?)```', r'{code}\1{code}', content)


# Based on https://gist.github.com/unbracketed/3380407
def write_issues(r, issues_csv, comments_csv, attachments_csv, repo):
    for issue in r.json():
        labels = []
        labels_lowercase = []
        for label in issue['labels']:
            label_name = label.get('name')
            if not label_name:
                continue
            labels.append(label_name)
            labels_lowercase.append(label_name)

        assignee = issue['assignee']
        if assignee:
            assignee = get_user_info(assignee)
        else:
            assignee = ""

        created = issue['created_at']
        updated = issue.get('updated_at', '')
        resolved = issue.get('closed_at', '')

        project = get_last_part_of_url(repo).replace('-', '_')
        author = get_user_info(issue['user'])

        milestone = issue.get('milestone')
        if milestone:
            milestone = milestone['title']
        else:
            milestone = ''

        state = issue['state'].lower()
        if state == 'closed':
            if 'wontfix' in labels_lowercase or 'invalid' in labels_lowercase:
                state = "Won't fix"
            else:
                state = "Fixed"
        if state == 'open' and 'in progress' in labels_lowercase:
            state == 'In Progress'

        issue_type = 'Task'
        if 'bug' in labels_lowercase:
            issue_type = 'Bug'
        elif 'feature' in labels_lowercase or 'features' in labels_lowercase:
            issue_type = 'Feature'

        issue_desc, image_links = process_attachments(issue['body'])
        for name, href in image_links:
            attach_row = [project, issue['number'], author, created, href, name]
            attachments_csv.writerow([utf8encode(e) for e in attach_row])

        # Convert markdown code blocks
        issue_desc = convert_code_blocks(issue_desc)
        # Add link to original GitHub issue
        issue_desc = '[%s GitHub Issue]\n\n' % issue['html_url'] + issue_desc

        issue_row = [project, project, issue['number'], state, issue['title'],
                     issue_desc, created, updated, resolved, author, assignee,
                     csvClient.VALUE_DELIMITER.join(labels), issue_type,
                     milestone]
        issues_csv.writerow([utf8encode(e) for e in issue_row])
        
        if int(issue.get('comments', 0)) > 0 and 'comments_url' in issue:
            rc = req_get(issue['comments_url'])
            for comment in rc.json():
                comment_text, image_links = process_attachments(comment['body'])
                # Convert markdown code blocks
                comment_text = convert_code_blocks(comment_text)
                comment_author = get_user_info(comment['user'])
                comment_row = [project, issue['number'], comment_author,
                               comment['created_at'], comment_text]
                comments_csv.writerow([utf8encode(e) for e in comment_row])
                for name, href in image_links:
                    attach_row = [project, issue['number'], comment_author,
                                  comment['created_at'], href, name]
                    attachments_csv.writerow(
                        [utf8encode(e) for e in attach_row])


def github2csv(issues_csv_file, comments_csv_file, attachments_csv_file,
               github_repo, github_repo_owner):
    #return None
    issues_url = 'https://api.github.com/repos/%s/%s/issues?state=all' % \
                 (github_repo_owner, github_repo)

    r = req_get(issues_url)

    issues_csv = csv.writer(open(issues_csv_file, 'wb'))
    issues_csv.writerow(
        ('Project Name', 'Project Id', 'Id', 'State', 'Summary', 'Description',
         'Created', 'Updated', 'Resolved', 'Author', 'Assignee', 'Labels',
         'Type', 'Milestone'))
    comments_csv = csv.writer(open(comments_csv_file, 'wb'))
    attachments_csv = csv.writer(open(attachments_csv_file, 'wb'))
    write_issues(r, issues_csv, comments_csv, attachments_csv, github_repo)

    # more pages? examine the 'link' header returned
    if 'link' in r.headers:
        pages = dict(
            [(rel[6:-1], url[url.index('<')+1:-1]) for url, rel in
                [link.split(';') for link in
                    r.headers['link'].split(',')]])
        while 'last' in pages and 'next' in pages:
            r = req_get(pages['next'])
            write_issues(
                r, issues_csv, comments_csv, attachments_csv, github_repo)
            pages = dict(
                [(rel[6:-1], url[url.index('<') + 1:-1]) for url, rel in
                 [link.split(';') for link in
                  r.headers['link'].split(',')]])


if __name__ == "__main__":
    main()
