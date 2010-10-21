#!/usr/bin/python

import cherrypy
import lg_authority

lg_authority.tool.register_as('auth')

#Test that register_as works as expected
@cherrypy.config(**{'auth.groups': ['auth']})
class TestAlias(object):
    @cherrypy.expose
    def index(self):
        return "You must be logged in to see this, {user.groups}!".format(user=cherrypy.user)

    @cherrypy.expose
    @lg_authority.groups('None')
    def deny(self):
        return "You can't see this or else you're cheating!"

cherrypy.tree.mount(TestAlias(), '/')
cherrypy.tree.mount(lg_authority.AuthRoot(), '/auth')
cherrypy.config.update({ 
    'server.socket_host': '0.0.0.0'
    , 'server.socket_port': 8081 
    , 'tools.lg_authority.on': True
    , 'tools.sessions.on': True
    })
cherrypy.engine.start()
cherrypy.engine.block()

