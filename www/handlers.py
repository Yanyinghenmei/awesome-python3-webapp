
import re, time, json, logging, hashlib, base64, asyncio
import apis
from config import configs
from coroweb import get, post
from aiohttp import web
from models import User, Comment, Blog, next_id


COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

# @get('/')
# async def index(request):
#     users = await User.findAll()
#     return {
#         '__template__':'test.html',
#         'users':users
#     }

@get('/')
async def index(request):
     summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
     blogs = [
         Blog(id='1',name='Test Blog', summary=summary, create_at=time.time()-120),
         Blog(id='2',name='Something New', summary=summary, create_at=time.time()-3600),
         Blog(id='3',name='Learn Swift', summary=summary, create_at=time.time()-7200),
     ]
     return {
         '__template__': 'blogs.html',
         'blogs': blogs
     }

@get('/api/users')
async def api_get_users(page='1',page_size='10',**kw):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    
    p = apis.Page(num,page_index,page_size=int(page_size))
    if num == 0:
        return dict(page=p,user=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    for u in users:
        u.passwd='******'
        # u['passwd'] = '******'
    return dict(page=p, users=users)


_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')

@get('/register')
async def register():
    return {
        '__template__': 'register.html'
    }

@get('/signin')
async def signin():
    return {
        '__template__': 'signin.html'
    }

@post('/api/register')
def api_register(*, email, name, passwd):
    if not name or not name.strip():
        raise apis.APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise apis.APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise apis.APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise apis.APIError('register: failed', 'email', 'Email is already in use.')
    uid = next_id
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid,name=name.strip(),email=email,passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save
    r =web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user,86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r

@post('/api/signin')
def api_signin():
    pass
    
    
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p



def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if collkie is valid
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None
