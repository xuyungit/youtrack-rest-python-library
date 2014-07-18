#! /usr/bin/env python

# migrate project from youtrack to youtrack
import os
import sys
from youtrack.connection import Connection, youtrack
#from sets import Set
import traceback

#httplib2.debuglevel=4
from sync.users import UserImporter
from sync.links import LinkImporter

import re
import getopt

convert_period_values = False
days_in_a_week = 5
hours_in_a_day = 8


def usage():
    print """
Usage:
    %s [-p] [-t TIME_SETTINGS] s_url s_user s_pass t_url t_user t_pass [project_id ...]

    s_url         Source YouTrack URL
    s_user        Source YouTrack user
    s_pass        Source YouTrack user's password
    t_url         Target YouTrack URL
    t_user        Target YouTrack user
    t_pass        Target YouTrack user's password
    project_id    ProjectID to import

Options:
    -h,  Show this help and exit
    -p,  Covert period values (used as workaroud for JT-19362)
    -t,  Time Tracking settings in format "days_in_a_week:hours_in_a_day"
""" % os.path.basename(sys.argv[0])

def main():
    global convert_period_values
    global days_in_a_week
    global hours_in_a_day
    try:
        params = {}
        opts, args = getopt.getopt(sys.argv[1:], 'hpt:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            if opt == '-p':
                convert_period_values = True
            elif opt == '-t':
                if ':' in val:
                    d, h = val.split(':')
                    if d:
                        days_in_a_week = int(d)
                    if h:
                        hours_in_a_day = int(h)
                else:
                    days_in_a_week = int(val)
        (source_url, source_login, source_password,
         target_url, target_login, target_password) = args[:6]
        project_ids = args[6:]
    except getopt.GetoptError, e:
        print e
        usage()
        sys.exit(1)
    except ValueError, e:
        print 'Not enough arguments'
        usage()
        sys.exit(1)
    youtrack2youtrack(source_url, source_login, source_password,
                      target_url, target_login, target_password, project_ids)

def create_bundle_from_bundle(source, target, bundle_name, bundle_type, user_importer):
    source_bundle = source.getBundle(bundle_type, bundle_name)
    # here we should check whether target YT has bundle with same name. But actually, to check tis, we should
    # get all bundles of every field type. So here we'll do a hack: just check if there is a bundle of bundle_type
    # type with this name, if there is bundle of another type -- there will be conflict, and we'll just exit with
    # corresponding message, as we can't proceed import anyway
    target_bundle_names = [bundle.name.strip() for bundle in target.getAllBundles(bundle_type)]
    if bundle_name in target_bundle_names:
        target_bundle = target.getBundle(bundle_type, bundle_name)
        if isinstance(source_bundle, youtrack.UserBundle):
            # get users and try to import them
            user_importer.importUsersRecursively(set(source_bundle.get_all_users()))
            # get field and calculate not existing groups
            target_bundle_group_names = [elem.name.capitalize() for elem in target_bundle.groups]
            groups_to_add = [group for group in target_bundle.groups if
                             group.name.capitalize() not in target_bundle_group_names]
            for group in groups_to_add:
                target.addValueToBundle(target_bundle, group)
                # add individual users to bundle
            source_bundle_user_logins = [elem.login.capitalize() for elem in source_bundle.users]
            users_to_add = [user for user in target_bundle.users if
                            user.login.capitalize() not in source_bundle_user_logins]
            for user in users_to_add:
                target.addValueToBundle(target_bundle, user)
            return
        target_value_names = [element.name.encode('utf-8').capitalize() for element in target_bundle.values]
        for value in [elem for elem in source_bundle.values if
                      elem.name.encode('utf-8').strip().capitalize() not in target_value_names]:
            target.addValueToBundle(target_bundle, value)
    else:
        users = set([])
        groups = []
        if isinstance(source_bundle, youtrack.UserBundle):
            groups = source_bundle.groups
            users = set(source_bundle.get_all_users())
        elif isinstance(source_bundle, youtrack.OwnedFieldBundle):
            users = set([source.getUser(elem.owner) for elem in source_bundle.values if elem.owner is not None])
        user_importer.importUsersRecursively(users)
        user_importer.importGroupsWithoutUsers(groups)
        print target.createBundle(source_bundle)

def create_project_custom_field(target, field, project_id):
    params = dict([])
    if hasattr(field, "bundle"):
        params["bundle"] = field.bundle
    emptyFieldText = "No " + field.name.lower()
    if hasattr(field, "emptyFieldText"):
        emptyFieldText = field.emtyFieldText
    target.createProjectCustomFieldDetailed(project_id, field.name, emptyFieldText, params)

def create_project_stub(source, target, projectId, user_importer):
    project = source.getProject(projectId)

    print "Create project stub [" + project.name + "]"
    lead = source.getUser(project.lead)

    print "Create project lead [" + lead.login + "]"
    user_importer.importUser(lead)

    try:
        target.getProject(projectId)
    except youtrack.YouTrackException:
        target.createProject(project)

    return target.getProject(projectId)

def enable_time_tracking(source, target, project_id):
    dst_settings = target.getProjectTimeTrackingSettings(project_id)
    if dst_settings:
        f_est = None
        f_spent = None
        src_settings = source.getProjectTimeTrackingSettings(project_id)
        # 1. If no settings available then there is YouTrack <= 4.2.1
        # 2. Do not override existing field settings.
        if src_settings and \
           not (dst_settings.EstimateField or dst_settings.TimeSpentField):
                f_est = src_settings.EstimateField
                f_spent = src_settings.TimeSpentField
        if src_settings.Enabled:
            print "Enabling Time Tracking"
            target.setProjectTimeTrackingSettings(project_id, f_est, f_spent, True)
            return True
    return False

def period_to_minutes(value):
    minutes = 0
    for period in re.findall('\d+[wdhm]', value):
        punit = period[-1]
        pvalue = int(period[:-1])
        if punit == 'm':
            minutes += pvalue
        elif punit == 'h':
            minutes += pvalue * 60
        elif punit == 'd':
            minutes += pvalue * hours_in_a_day * 60
        elif punit == 'w':
            minutes += pvalue * days_in_a_week * hours_in_a_day * 60
    return str(minutes)


def youtrack2youtrack(source_url, source_login, source_password, target_url, target_login, target_password,
                      project_ids, query = ''):
    if not len(project_ids):
        print "You should sign at least one project to import"
        return

    source = Connection(source_url, source_login, source_password)
    target = Connection(target_url, target_login,
        target_password) #, proxy_info = httplib2.ProxyInfo(socks.PROXY_TYPE_HTTP, 'localhost', 8888)

    print "Import issue link types"
    for ilt in source.getIssueLinkTypes():
        try:
            print target.createIssueLinkType(ilt)
        except youtrack.YouTrackException, e:
            print e.message

    user_importer = UserImporter(source, target, caching_users=True)
    link_importer = LinkImporter(target)

    #create all projects with minimum info and project lead set
    created_projects = []
    for project_id in project_ids:
        created = create_project_stub(source, target, project_id, user_importer)
        created_projects.append(created)

    #save created project ids to create correct group roles afterwards
    user_importer.addCreatedProjects([project.id for project in created_projects])
    #import project leads with group they are included and roles assigned to these groups
    user_importer.importUsersRecursively([target.getUser(project.lead) for project in created_projects])
    #afterwards in a script any user import imply recursive import

    cf_names_to_import = set([]) # names of cf prototypes that should be imported
    for project_id in project_ids:
        cf_names_to_import.update([pcf.name.capitalize() for pcf in source.getProjectCustomFields(project_id)])

    target_cf_names = [pcf.name.capitalize() for pcf in target.getCustomFields()]

    period_cf_names = []

    for cf_name in cf_names_to_import:
        source_cf = source.getCustomField(cf_name)
        if source_cf.type.lower() == 'period':
            period_cf_names.append(source_cf.name.lower())

        if cf_name in target_cf_names:
            target_cf = target.getCustomField(cf_name)
            if not(target_cf.type == source_cf.type):
                print "In your target and source YT instances you have field with name [ %s ]" % cf_name.encode('utf-8')
                print "They have different types. Source field type [ %s ]. Target field type [ %s ]" %\
                      (source_cf.type, target_cf.type)
                print "exiting..."
                exit()
        else:
            if hasattr(source_cf, "defaultBundle"):
                create_bundle_from_bundle(source, target, source_cf.defaultBundle, source_cf.type, user_importer)
            target.createCustomField(source_cf)

    for projectId in project_ids:
        source = Connection(source_url, source_login, source_password)
        target = Connection(target_url, target_login,
            target_password) #, proxy_info = httplib2.ProxyInfo(socks.PROXY_TYPE_HTTP, 'localhost', 8888)
        #reset connections to avoid disconnections
        user_importer.resetConnections(source, target)
        link_importer.resetConnections(target)

        # copy project, subsystems, versions
        project = source.getProject(projectId)

        link_importer.addAvailableIssuesFrom(projectId)
        project_custom_fields = source.getProjectCustomFields(projectId)
        # create bundles and additional values
        for pcf_ref in project_custom_fields:
            pcf = source.getProjectCustomField(projectId, pcf_ref.name)
            if hasattr(pcf, "bundle"):
                create_bundle_from_bundle(source, target, pcf.bundle, source.getCustomField(pcf.name).type, user_importer)

        target_project_fields = [pcf.name for pcf in target.getProjectCustomFields(projectId)]
        for field in project_custom_fields:
            if field.name in target_project_fields:
                if hasattr(field, 'bundle'):
                    if field.bundle != target.getProjectCustomField(projectId, field.name).bundle:
                        target.deleteProjectCustomField(projectId, field.name)
                        create_project_custom_field(target, field, projectId)
            else:
                create_project_custom_field(target, field, projectId)

        # copy issues
        start = 0
        max = 20

        sync_workitems = enable_time_tracking(source, target, project_id)

        print "Import issues"

        while True:
            try:
                print "Get issues from " + str(start) + " to " + str(start + max)
                issues = source.getIssues(projectId, query, start, max)

                if len(issues) <= 0:
                    break

                if convert_period_values and period_cf_names:
                    for issue in issues:
                        for pname in period_cf_names:
                            for fname in issue.__dict__:
                                if fname.lower() != pname:
                                    continue
                                issue[fname] = period_to_minutes(issue[fname])

                users = set([])

                for issue in issues:
                    print "Collect users for issue [ " + issue.id + "]"

                    users.add(issue.getReporter())
                    if issue.hasAssignee(): users.add(issue.getAssignee())
                    #TODO: http://youtrack.jetbrains.net/issue/JT-6100
                    users.add(issue.getUpdater())
                    if issue.hasVoters(): users.update(issue.getVoters())
                    for comment in issue.getComments(): users.add(comment.getAuthor())

                    print "Collect links for issue [ " + issue.id + "]"
                    link_importer.collectLinks(issue.getLinks(True))
                    #links.extend(issue.getLinks(True))

                    # fix problem with comment.text
                    for comment in issue.getComments():
                        if not hasattr(comment, "text") or (len(comment.text.strip()) == 0):
                            setattr(comment, 'text', 'no text')

                user_importer.importUsersRecursively(users)

                print "Create issues [" + str(len(issues)) + "]"
                print target.importIssues(projectId, project.name + ' Assignees', issues)
                link_importer.addAvailableIssues(issues)

                for issue in issues:
                    if sync_workitems:
                        workitems = source.getWorkItems(issue.id)
                        if workitems:
                            print "Process workitems for issue [ " + issue.id + "]"
                            try:
                                target.importWorkItems(issue.id, workitems)
                            except youtrack.YouTrackException, e:
                                if e.response.status == 404:
                                    print "WARN: Target YouTrack doesn't support workitems importing."
                                    print "WARN: Workitems won't be imported."
                                    sync_workitems = False
                                else:
                                    print "ERROR: Skipping workitems because of error:" + str(e)

                    print "Process attachments for issue [ " + issue.id + "]"
                    attachments = issue.getAttachments()
                    users = set([])

                    for a in attachments:
                        author = a.getAuthor()
                        if author is not None:
                            users.add(author)
                    user_importer.importUsersRecursively(users)

                    for a in attachments:
                        print "Transfer attachment of " + issue.id.encode('utf-8') + ": " + a.name.encode('utf-8')
                        # TODO: add authorLogin to workaround http://youtrack.jetbrains.net/issue/JT-6082
                        #a.authorLogin = target_login
                        try:
                            target.createAttachmentFromAttachment(issue.id, a)
                        except BaseException, e:
                            print("Cant import attachment [ %s ]" % a.name.encode('utf-8'))
                            print repr(e)

            except Exception, e:
                print('Cant process issues from ' + str(start) + ' to ' + str(start + max))
                traceback.print_exc()
                raise e

            start += max

    print "Import issue links"
    link_importer.importCollectedLinks()


if __name__ == "__main__":
    main()
