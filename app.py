
import logging
import asyncio, os, json, time
from datetime import  datetime
from aiohttp import web
logging.basicConfig(level=logging.INFO)


def index(request):
    return web.Response(body=b'<h1>Awesome</h1>', content_type='text/html')


async def init(loop):
    app = web.Application(loop=loop)
    app.router.add_route('GET', '/', index)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 9000)
    await site.start()
    print('Server started at http://127.0.0.1:9000...')
    return site


loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()


