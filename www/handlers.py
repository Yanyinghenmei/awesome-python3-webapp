
import re, time, json, logging, hashlib, base64, asyncio
from apis import Page
from coroweb import get, post

from models import User, Comment, Blog, next_id

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
    
    p = Page(num,page_index,page_size=int(page_size))
    if num == 0:
        return dict(page=p,user=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset,p.limit))
    for u in users:
        u.passwd='******'
        # u['passwd'] = '******'
    return dict(page=p, users=users)
    
    
def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p
