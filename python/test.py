from youtrack.connection import Connection
from youtrack import User

connection = Connection("http://bootster.myjetbrains.com/youtrack", "boot85", "boot85")
#xml = open('/home/user/test.xml', 'r').read()
#connection.importIssuesXml("A", "A assignees", xml)
print connection.createUserDetailed("b", "c", "d", "jj")

class A:
    def _do_smth(self):
        pass


class B(A):
    pass
