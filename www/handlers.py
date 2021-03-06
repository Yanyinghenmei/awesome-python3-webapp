
import re, time, json, logging, hashlib, base64, asyncio
import apis
import markdown2
from config import configs
from coroweb import get, post
from aiohttp import web
from models import User, Comment, Blog, next_id


COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

@get('/')
async def index(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    page = apis.Page(num, page_index)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__template__': 'blogs.html',
        'page': page,
        'blogs': blogs
    }


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

@get('/signout')
def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    logging.info('user signed out.')
    return r

@get('/manage/') # manage by Administrator
def manage():
	return 'redirect: /manage/blogs'

@get('/manage/blogs')
def manage_blogs(*, page='1'):
    return {
        '__template__': 'manage_blogs.html',
        'page_index': get_page_index(page)
    }


@get('/blog/{id}')
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?',[id], orderBy='created_at desc')
    if blog == None:
        raise apis.APIResourceNotFoundError('blog')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__template__': 'blog.html',
        'blog': blog,
        'comments': comments
    }


@get('/manage/blogs/create')
def manage_create_blog():
    return {
        '__template__': 'manage_blog_edit.html',
        'id': '',
        'action': '/api/blogs/create',
    }

@get('/manage/blogs/edit')
def manage_edit_blog(*, id):
    return {
        '__template__': 'manage_blog_edit.html',
        'id': id,
        'action': '/api/blogs/create'
    }


@get('/manage/comments')
def manage_comments(*, page = '1'):
    return {
        '__template__': 'manage_comments.html',
        'page_index': get_page_index(page)
    }

# ============= API =====================
_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


# ============================ users ============================
# 用户列表
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

@post('/api/users/{id}/delete')
async def api_delete_users(id, request):
    check_admin(request)
    user = await User.find(id)
    if user is None:
        raise apis.APIResourceNotFoundError('user')
    await user.remove()
    # 为被删除用户的评论进行标记
    comments = await Comment.findAll('user_id=?',[id])
    if comments:
        for comment in comments:
            comment.user_name = comment.user_name + '(该用户已被删除)'
            await comment.update()
    
    return dict(id=id)

# 注册
@post('/api/register')
async def api_register(*, email, name, passwd):
    if not name or not name.strip():
        raise apis.APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise apis.APIValueError('email')
    if not passwd or not _RE_SHA1.match(passwd):
        raise apis.APIValueError('passwd')
    users = await User.findAll('email=?', [email])
    if len(users) > 0:
        raise apis.APIError('register: failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_passwd = '%s:%s' % (uid, passwd)
    user = User(id=uid,name=name.strip(),email=email,passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
    await user.save()
    r =web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user,86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


# 登录
@post('/api/signin')
async def api_signin(*, email, passwd):
    if not email:
        raise apis.APIValueError('email', 'Invalid email')
    if not passwd:
        raise apis.APIValueError('passwd', 'Invalid password')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise apis.APIValueError('email', 'Email not exist')
    user = users[0]
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise apis.APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user,86400), max_age=86400, httponly=True)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


# =========================== comments ===============================    
@get('/api/comments')
async def api_comments(*, page = '1'):
    page_index = get_page_index(page)
    num = await Comment.findNumber('count(id)')
    p = apis.Page(num, page_index)
    if num == 0:
        return dict(page = p, comments = ())
    comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    for comment in comments:
        # 找到对应文章
        id = comment.blog_id
        blog = await Blog.find(id)
        comment['blog_name'] = blog.name
    return dict(page=p, comments=comments)

@post('/api/comments/{id}/delete')
async def api_delete_comments(id, request):
    check_admin(request)
    c = await Comment.find(id)
    if c is None:
        raise apis.APIResourceNotFoundError('Comment')
    await c.remove()
    return dict(id=id)

@post('/api/blogs/{id}/comments/create')
async def api_create_comment(id, request, *, content):
    user = request.__user__
    if user is None:
        raise apis.APIPermissionError('please signin first.')
    if not content:
        raise apis.APIValueError('content')
    blog = await Blog.find(id)
    if blog is None:
        raise apis.APIResourceNotFoundError('Blog')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image,content=content.strip())
    await comment.save()
    return comment

# =========================== bolgs ===============================
# 请求blogs列表
@get('/api/blogs')
async def api_blogs(*, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = apis.Page(num, page_index)
    if num == 0:
        return dict(page=p,blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    return dict(page=p,blogs=blogs)
    
# 请求blog
@get('/api/blogs/{id}')
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    # comments = Comment.findall('blog_id?', [id], orderBy='created_at desc')
    # for c in comments:
    #     c.html_content=
    return blog

# 创建blog
@post('/api/blogs/create')
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise apis.APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise apis.APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise apis.APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog

@post('/api/blogs/{id}/update')
async def api_update_blog(id, request, *, name, summary, content):
    check_admin(request)
    blog = await Blog.find(id)
    if blog == None:
        raise apis.APIResourceNotFoundError('blog')
    if not name or not name.strip():
        raise apis.APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise apis.APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise apis.APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog
    
@post('/api/blogs/{id}/delete')
async def api_delete_blog(request, *, id):
    check_admin(request)
    blog = await Blog.find(id)
    await blog.remove()
    comments = await Comment.findAll('blog_id=?', [id])
    for comment in comments:
        await comment.remove()
    return dict(id=id)


#  ================= TOOLS ===================

def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise apis.APIPermissionError()

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
	# build cookie string by: id-expires-sha1
	expires = str(int(time.time() + max_age))
	s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
	L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
	return '-'.join(L)

async def cookie2user(cookie_str):
	'''
	Parse cookie and load user if cookie is valid.
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

def text2html(text):
	lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'), filter(lambda s: s.strip() != '', text.split('\n')))
	return ''.join(lines)