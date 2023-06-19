from views import index, restart
from auth  import Login, SignIn, SignOut

routes = [
    ('GET', '/',        index,   'main'),
    ('GET', '/Restart', restart, 'restart'),
    ('*',   '/login',   Login,   'login'),
    ('*',   '/signin',  SignIn,  'signin'),
    ('*',   '/signout', SignOut, 'signout'),
]