__author__ = 'user'
import httplib2
import json

class ZendeskClient:
    def __init__(self, url, login, password):
        self._http = httplib2.Http(disable_ssl_certificate_validation=True)
        self._url = url
        self._http.add_credentials(login, password)

    def _rest_url(self):
        return self._url + "/api/v2"

    def get_issues(self, after, limit):
        response, content = self._get("/tickets.json?page=" + str(after / limit) + "&per_page=" + str(limit))
        if response.status == 200:
            tickets = content[u'tickets']
            org_id_key = u'organization_id'
            for t in tickets:
                org_id = t.get(org_id_key)
                if org_id is not None:
                    t[org_id_key] = self.get_organization(org_id)[u'name']
            return tickets

    def get_custom_fields(self):
        response, content = self._get("/ticket_fields.json")
        if response.status == 200:
            return content[u'ticket_fields']

    def get_organization(self, id):
        response, content = self._get("/organizations/" + str(id) + ".json")
        if response.status == 200:
            return content[u'organization']


    def get_user(self, id):
        response, content = self._get("/users/" + str(id) + ".json")
        if response.status == 200:
            return content[u'user']

    def get_groups_for_user(self, id):
        response, content = self._get("/users/" + str(id) + "/group_memberships.json")
        if response.status == 200:
            result = []
            for membership in content["group_memberships"]:
                group = self.get_group(membership["group_id"])
                result.append(group["name"])
            return result

    def get_group(self, id):
        response, content = self._get("/groups/" + str(id) + ".json")
        if response.status == 200:
            return content[u'group']


    def _get(self, url):
        response, content = self._http.request(self._rest_url() + url)
        return response, json.loads(content)

