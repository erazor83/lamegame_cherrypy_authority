import cherrypy

from .common import *

class AuthTool(cherrypy.Tool):
    """Authentication tool for CherryPy.  Called with various parameters
    to enforce different restrictions on a resource.  

    If the user is found to be logged in, cherrypy.user.slate will be set to
    the user's slate if lamegame_cherrypy_slates is also installed.  Otherwise,
    cherrypy.user.slate will be set to cherrypy.session['slate'].
    """

    aliases = []

    def __init__(self):
        """Setup the tool configuration"""
        self._name = 'lg_authority'

    def register_as(self, name):
        """Adds an alias for this tool; may be called multiple times.
        e.g. cherrypy.tools.lg_authority.register_as('auth') allows things 
        like auth.groups instead of tools.lg_authority.groups in your 
        config files.
        """
        self.aliases.append(name)

    def _merged_args(self):
        """Since we have aliases and a base config dict, we merge our
        own arguments.
        """
        #Merge conf out of the default configuration, aliased configurations,
        #and tools configuration.
        base_dict = config.copy()
        for name in self.aliases:
            namestart = name + '.'
            lenstart = len(namestart)
            for k,v in cherrypy.request.config.items():
                if k.startswith(namestart):
                    base_dict[k[lenstart:]] = v
        return cherrypy.Tool._merged_args(self, base_dict)

    def _setup(self):
        """Hook into cherrypy.request.  Called automatically if turned on."""

        hooks = cherrypy.serving.request.hooks

        conf = self._merged_args()
        #Store request config for non-tools as well
        cherrypy.serving.lg_authority = conf
        p = conf.pop('priority', 60) #Priority should be higher than session
                                     #priority, since we read the session.
        hooks.attach('before_request_body', self.check_auth, priority=p, **conf)

        if hasattr(self, 'initialized'):
            return
        self.initialized = True

        #Set the site specific settings in config (Most params don't update the 
        #base config dict)
        for k,v in conf.items():
            if k.startswith('site_'):
                config[k] = v

        #Set up cherrypy.user
        if not hasattr(cherrypy, 'user'):
            cherrypy.user = cherrypy._ThreadLocalProxy('user')

        #Check for slates
        if cherrypy.config.get('tools.lg_slates.on', False):
            try:
                import lg_slates
                self._Slate = lg_slates.Slate
            except:
                self._Slate = None
        else:
            self._Slate = None

        #Set up the authentication system
        authtype = conf['site_authtype']
        config.authmodule = __import__(
            'lg_authority.authtypes.' + authtype
            , globals(), locals()
            , [ '*' ]
            )
        config.auth = config.authmodule.setup(conf['site_authtype_conf'])

    def check_auth(self, **kwargs):
        """Check for authenticated state, and setup user slate if applicable.

        Then validate permissions by group.
        """
        #Make the user into an object for conveniences
        user = cherrypy.session.get('auth', None)
        user = user and ConfigDict(user)
        cherrypy.serving.user = user
        if user is not None:
            user.name = user['name'] #Convenience
            user.groups = user['groups'] #Convenience
            if self._Slate is not None:
                user.slate = self._Slate(
                    kwargs['user_slate_prefix'] + user['name']
                    )
            else:
                #Rather than neutering cherrypy.user.slate, assign it to
                #part of the session if slates cannot be found.
                user.slate = cherrypy.session.setdefault(
                    kwargs['user_slate_prefix'] + 'slate'
                    , {}
                    )

        #Now validate static permissions, if any
        access_groups = kwargs['groups']
        if access_groups is not None:
            if len(access_groups) > 0 and access_groups[0] == 'all:':
                access_groups = access_groups[1:]
                check_groups_all(*access_groups)
            else:
                check_groups(*access_groups)

