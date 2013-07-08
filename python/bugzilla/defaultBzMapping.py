import bugzilla

bugzilla.FIELD_TYPES = {
    "created"           :   "date",
    "updated"           :   "date",
    "numberInProject"   :   "integer",
    "reporterName"      :   "user[1]",
    "Assignee"          :   "user[1]",
    "Subsystem"         :   "ownedField[1]",
    "Affected versions" :   "version[*]",
    "Severity"          :   "enum[1]",
    "Status"            :   "state[1]",
    "Resolution"        :   "state[1]",
    "Platform"          :   "enum[1]",
    "watcherName"       :   "user[*]",
    "voterName"         :   "user[*]",
    "Deadline"          :   "date",
    "Estimate"          :   "integer",
    "QA contact"        :   "user[1]",
    "Milestone"         :   "version[*]"
}

bugzilla.FIELD_NAMES = {
    "bug_id"            :   "numberInProject",
    "reporter"          :   "reporterName",
    "version"           :   "Affected versions",
    "voters"            :   "voterName",
    "assigned_to"       :   "Assignee",
    "bug_severity"      :   "Severity",
    "bug_status"        :   "Status",
    "creation_ts"       :   "created",
    "OS"                :   "Platform",
    "short_desc"        :   "summary",
    "cc"                :   "watcherName",
    "delta_ts"          :   "updated",
    "qa_contact"        :   "QA contact",
    "estimated_time"    :   "Estimate",
    "target_milestone"  :   "Milestone",
    "component"         :   "Subsystem",
}

# *** Import from Bugzilla v2.XX ***
#
# !!! Important notes !!!
#  1. You have to alter your Bugzilla database to make it possible to import your data.
#  2. We strongly recommend you to backup the database before you start.
#
# Execute these queries to alter your database:
#   alter table fielddefs add column `custom` tinyint(4) NOT NULL DEFAULT '0';
#   alter table fielddefs add column `type` smallint(6) NOT NULL DEFAULT '0';
#   alter table versions add column `id` mediumint(9) NOT NULL DEFAULT '0';
#
# Also, please uncomment the bugzilla.FIELD_NAMES block below and comment the same block above.
#
#bugzilla.FIELD_NAMES = {
#    "bug_id"            :   "numberInProject",
#    "reporter"          :   "reporterName",
#    "version"           :   "Affected versions",
#    "voters"            :   "voterName",
#    "assigned_to"       :   "Assignee",
#    "bug_severity"      :   "Severity",
#    "bug_status"        :   "Status",
#    "creation_ts"       :   "created",
#    "op_sys"            :   "Platform",
#    "short_desc"        :   "summary",
#    "cc"                :   "watcherName",
#    "delta_ts"          :   "updated",
#    "qa_contact"        :   "QA contact",
#    "estimated_time"    :   "Estimate",
#    "target_milestone"  :   "Milestone",
#    "component"         :   "Subsystem",
#}

# mapping between cf types in bz and youtrack
bugzilla.CF_TYPES = {
    "1"             :   "string",   #FIELD_TYPE_FREETEXT
    "2"             :   "enum[1]",  #FIELD_TYPE_SINGLE_SELECT
    "3"             :   "enum[*]",  #FIELD_TYPE_MULTY_SELECT
    "4"             :   "string",   #FIELD_TYPE_TEXTAREA
    "5"             :   "date",     #FIELD_TYPE_DATETIME
    "7"             :   "string"    #FIELD_TYPE_BUG_URLS
}


# if we need to import empty comments
bugzilla.ACCEPT_EMPTY_COMMENTS = False
bugzilla.BZ_DB_CHARSET = 'utf8'
