__author__ = 'user'
ESCAPE_DCT = {
    '\\': '\\\\',
    '"': '\\"',
    '\b': '\\b',
    '\f': '\\f',
    '\n': '\\n',
    '\r': '\\r',
    '\t': '\\t',
}
for i in range(0x20):
    ESCAPE_DCT.setdefault(chr(i), '\\u%0*x' % (4, i))

print ESCAPE_DCT


s1 = 0xd800
s2 = 0xdc00
print '\\u%0*x\\u%0*x' % ((4, s1), (4, s2))