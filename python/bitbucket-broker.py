#! /usr/bin/python

import sys
import os
import re
import getopt
import socket
from youtrack.connection import Connection
from youtrack import YouTrackException
try:
    from flask import Flask, request, abort, json
except ImportError as e:
    print 'The script depends on Flask package. Please install it first.\n'
    raise e


def get_commits_url_template(payload):
    repo = payload['repository']
    host = payload.get('canon_url', 'https://bitbucket.org')
    path = repo.get('absolute_url')
    if not path:
        path = '/' + repo['owner'] + '/' + repo['name'].lower() + '/'
    return host + path + 'commits/%s'


def generate_secret():
    return os.urandom(16).encode('hex')


def get_my_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('google.com', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except socket.error:
        return socket.gethostbyname(socket.gethostname())


def usage():
    basename = os.path.basename(sys.argv[0])
    print """
This broker processes requests about commits from the BitBucket POST hook.
To apply a command from a comment to a BitBucket commit, the following
comment syntax should be used:
[some comment text] #issue_id <command_1> [command_2] ... [command_n]
[some comment text] #issue_id <command_1> [command_2] ... [command_n]

Usage:
    %s [OPTIONS] <yt_base_url> <username> <password>

Options:
    -h, --help
            Show the help screen.

    -d, --debug
            Enable debug mode.

    -p, --port <source_port>
            Specifies the source port to use.

    -c, --context
            Context path to process POST request from the BitBucket hook.
            It can contain a secret part ('/<context>/<secret>').
            To set secret use the following option: -s, --secret.

    -s, --secret <secret>
            Adds the specified secret to context.

    -g, --gen-secret
            Generate and print secret that can be used as part of context.

Examples:
    $ %s --gen-secret
    508ac3baab155906b38df70e7c1cb06d

    $ %s -s 508ac3baab155906b38df70e7c1cb06d http://yt.host.com root root
    ...

    $ %s --context bitbucket --secret 123 http://yt.host.com root root
    ...

""" % ((basename, ) * 4)


def main():
    debug = False
    port = 5000
    context = '/'
    context_secret = None

    opts, args = getopt.getopt(
        sys.argv[1:],
        'hdgs:p:c:',
        ['help', 'debug', 'context=', 'gen-secret', 'secret=', 'port='])
    for o, v in opts:
        if o in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif o in ('-d', '--debug'):
            debug = True
        elif o in ('-g', '--gen-secret'):
            print generate_secret()
            sys.exit(0)
        elif o in ('-s', '--secret'):
            context_secret = v
        elif o in ('-p', '--port'):
            port = int(v)
        elif o in ('-c', '--context'):
            context += v.strip('/')

    my_url = 'http://%s:%d%s' % (get_my_ip(), port, context.rstrip('/'))
    if context_secret:
        context += '/<secret>'
        my_url += '/' + context_secret

    if len(args) < 3:
        print 'Not enough arguments'
        sys.exit(1)

    yt_url, yt_login, yt_password = args[0:3]

    app = Flask(__name__)
    
    @app.route(context, methods=['POST'])
    def process_commits(secret=None):
        if context_secret and secret != context_secret:
            abort(403)
        yt = Connection(yt_url, yt_login, yt_password)
        try:
            cmd_pattern = re.compile(
                r'#((?:%s)-\d+)(?:\s+(.+))?' % '|'.join(yt.getProjects().keys()),
                re.IGNORECASE | re.MULTILINE)
        except YouTrackException:
            app.logger.warning('Cannot get projects from YT')
            cmd_pattern = re.compile(r'#([A-z]+-\d+)(?:\s+(.+))?', re.MULTILINE)
        payload = json.loads(request.form.get('payload'))
        commits_url_template = get_commits_url_template(payload)
        for commit in payload['commits']:
            message = commit['message'].encode('utf-8')
            issue_refs = cmd_pattern.findall(message)
            if not issue_refs:
                continue
            commit_node = commit['node']
            commit_url = commits_url_template % commit['raw_node']
            timestamp = commit['utctimestamp']
            author = commit['author'].encode('utf-8')
            match = re.search(r'<(.+?)>', commit['raw_author'])
            if not match:
                app.logger.error("Cannot get author's email address.")
                abort(400)
            users = yt.getUsers(params={'q': match.group(1)})
            if not users:
                app.logger.error('Cannot find user with email ' + match.group(1))
                abort(400)
            if len(users) != 1:
                app.logger.error('Not unique email address ' + match.group(1))
                abort(400)
            comment = "Commit [%s %s] made by '''%s''' on ''%s''\n{quote}%s{quote}" \
                      % (commit_url, commit_node, author, timestamp, message)
            cmd_exec_result = True
            for issue_id, command in issue_refs:
                if command is None:
                    command = ''
                try:
                    app.logger.info("Adding commit %s to issue %s (command: %s)" %
                                    (commit_node, issue_id, command))
                    yt.executeCommand(issue_id, command, comment, run_as=users[0].login)
                except YouTrackException as e:
                    cmd_exec_result = False
                    app.logger.error('Failed to add commit %s to issue %s: %s' %
                                     (commit_node, issue_id, e.message))
            if not cmd_exec_result:
                abort(500)
        return 'success'

    print '-' * 80
    print ' POST hook URL (the real ip/hostname can be different):'
    print '', my_url
    print '-' * 80
    app.run(host='0.0.0.0', debug=debug, port=port)


if __name__ == '__main__':
    main()