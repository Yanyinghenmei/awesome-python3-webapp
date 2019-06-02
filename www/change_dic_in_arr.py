

from models import User


class Person(object):
    def __init__(self):
        self.name = 'aaaaa'



p0 = Person()
p1 = User(name='Test', email='test@example3.com', passwd='1234567890', image='about:blank')
p2 = User(name='Test', email='test@example3.com', passwd='1234567890', image='about:blank')
a = (p1,p2)

for p in a:
    p.name = 'daniel'

print(a)

for p in a:
    print(p.name,p['name'])
    print(p)