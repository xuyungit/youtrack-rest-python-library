import itertools

l = (i for i in range(100))
for i in range(10):
    print list(itertools.islice(l, None, 10))