"""Non-persistent user store that is configured entirely through
CherryPy's configuration methods.
"""

from .common import AuthInterface

class UserListInterface(AuthInterface):
    def __init__(self, options):
        self.options = options
        self.users = options['users']

    def get_user_record(self, username):
        user = self.users.get(username)
        if user is not None:
            return {
                'name': username
                ,'groups': user.get('groups', [])
                }
        return None

    def get_user_password(self, username):
        user = self.users.get(username)
        p = None
        if user is not None:
            p = user.get('auth', {}).get('password', None)
        return p

def setup(options):
    return UserListInterface(options)

