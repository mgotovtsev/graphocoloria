import json
from time import time

import aiohttp_jinja2
from aiohttp import web
from aiohttp_session import get_session

dictUsers = dict()


def redirect(request, router_name):
    url = request.app.router[router_name].url_for().path
    raise web.HTTPFound(url)


def set_session(session, user_id, request):
    session['user'] = str(user_id)
    session['last_visit'] = time()
    redirect(request, 'main')


def convert_json(message):
    return json.dumps({'error': message})


class Login(web.View):

    @aiohttp_jinja2.template('auth/login.html')
    async def get(self):
        session = await get_session(self.request)
        if session.get('user'):
            redirect(self.request, 'main')
        return {'conten': 'Please enter login or email'}

    async def post(self):
        data = await self.request.post()
        sUserName = data['login']
        sPassword = data['password']
        dictUsers[sUserName] = sPassword
        session = await get_session(self.request)
        set_session(session, sUserName, self.request)


class SignIn(web.View):

    @aiohttp_jinja2.template('auth/sign.html')
    async def get(self, **kw):
        session = await get_session(self.request)
        if session.get('user'):
            redirect(self.request, 'main')
        return {'conten': 'Please enter your data'}

    async def post(self, **kw):
        data = await self.request.post()
        sUserName = data['login']
        sPassword = data['password']

        if sUserName in dictUsers[sUserName] and dictUsers[sUserName] == sPassword:
            session = await get_session(self.request)
            set_session(session, sUserName, self.request)
        else:
            return web.Response(content_type='application/json', text = convert_json('Login or password not found!'))


class SignOut(web.View):

    async def get(self, **kw):
        session = await get_session(self.request)
        if session.get('user'):
            del session['user']
            redirect(self.request, 'login')
        else:
            raise web.HTTPForbidden(body=b'Forbidden')





