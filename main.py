import logging

import jinja2
import hashlib

import aiohttp_jinja2

from middlewares import authorize
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from aiohttp import web

from routes import routes

SECRET_KEY='some secure key1'

async def init_app():

    middle = [
        session_middleware(EncryptedCookieStorage(hashlib.sha256(bytes(SECRET_KEY, 'utf-8')).digest())),
        authorize,
    ]

    app = web.Application(middlewares = middle)

    app['websockets'] = {}

    app.on_shutdown.append(shutdown)

    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates'))

    # route part
    for route in routes:
        app.router.add_route(route[0], route[1], route[2], name=route[3])
    app['static_root_url'] = '/static'
    app.router.add_static('/static', 'static', name='static')
    # end route part

    return app


async def shutdown(app):
    for ws in app['websockets'].values():
        await ws.close()
    app['websockets'].clear()


def main():
    logging.basicConfig(level=logging.DEBUG)

    app = init_app()
    web.run_app(app)


if __name__ == '__main__':
    main()
