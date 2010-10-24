"""The root for lg_authority web actions"""

import os
import datetime

import cherrypy

from .common import *
from .adminroot import AdminRoot
from .openidconsumer import OpenIdConsumerRoot
from . import passwords

@groups('any')
class AuthRoot(object):
    """The lg_authority class responsible for handling authentication."""

    static = cherrypy.tools.staticdir.handler(
        section='/static'
        ,dir='static'
        ,root=os.path.dirname(os.path.abspath(__file__))
        )

    admin = AdminRoot()

    def __init__(self):
        self.login_openid = OpenIdConsumerRoot(self)

    def login_redirect(self, user, redirect=None):
        """Raises cherrypy.HTTPRedirect to the appropriate location.
        Used by login handlers on success.
        """
        redirect = redirect or config['user_home_page']
        if hasattr(redirect, '__call__'):
            redirect = redirect(user)
        raise cherrypy.HTTPRedirect(redirect)

    @cherrypy.expose
    @groups('auth')
    def index(self):
        return '<div class="lg_auth_form"><p>You are logged in as {user.name}</p><p>You are a member of the following groups: {groups}</p></div>'.format(user=cherrypy.user, groups=get_user_groups_named())

    @cherrypy.expose
    def login(self, **kwargs):
        #Check for already logged in.  This allows page refreshes to login
        #if multiple tabs were open.
        if cherrypy.user:
            self.login_redirect(cherrypy.user, kwargs.get('redirect'))

        kwargs.setdefault('error', '')
        kwargs.setdefault('redirect', '')
        if config['site_registration'] is None:
            kwargs['new_account'] = """<p class="lg_auth_newaccount">
New accounts are not allowed.  Contact administrator if you need access.
</p>"""
        else:
            kwargs['new_account'] = """<p class="lg_auth_newaccount">
<a href="{0}">Don't have an account here?  Create one.</a>
</p>""".format(url_add_parms('new_account', { 'redirect': kwargs.get('redirect', '') }))

        if self.login_openid.supported:
            #Setup OpenID providers
            openid_list = []
            def add_provider(name, url):
                li = """<li><a href="{url}">{name}</a></li>""".format(
                    url = url_add_parms('login_openid', { 'url': url, 'redirect': kwargs['redirect'] })
                    ,name = name
                    )
                openid_list.append(li)

            add_provider('Google', 'https://www.google.com/accounts/o8/id')
            add_provider('Yahoo!', 'http://yahoo.com')
            openid_list.append("""<li><form method="GET" action="login_openid" class="lg_auth_openid_><input type="hidden" name="redirect" value="{redirect}"/>OpenID URL: <input style="width:20em;" type="text" name="url" value="http://"/><input type="submit" value="Submit"/></form></li>""".format(**kwargs))
            openid_list = ''.join(openid_list)
            kwargs['openid'] = """
<p class="lg_auth_select_openid">
  OpenID (have an account with any of these providers?  Click the appropriate icon to use it here):<ul>
    {openid_list}
  </ul>
</p>""".format(openid_list=openid_list)
        else:
            kwargs['openid'] = ''

        return """
<div class="lg_auth_form">
<span style="color:#ff0000;" class="lg_auth_error">{error}</span>
<form action="login_password" method="POST">
  <input type="hidden" name="redirect" value="{redirect}" />
  <p>
    Password Login:
    <table>
      <tr><td>Username</td><td><input type="text" name="username" /></td></tr>
      <tr><td>Password</td><td><input type="password" name="password" /></td></tr>
      <tr><td><input type="submit" value="Submit" /></td></tr>
    </table>
  </p>
</form>
{openid}
{new_account}
</form>
</div>
        """.format(**kwargs)

    @cherrypy.expose
    def logout(self):
        config.auth.logout()
        redirect = config['logout_page']
        if redirect:
            raise cherrypy.HTTPRedirect(redirect)
        return "You have logged out."
        
    @cherrypy.expose
    def new_account_ok(self, redirect=''):
        #TODO - replace redir_wait with registration method's message.
        redir_wait = """<p>Registration complete.</p>"""
        redir_link = ''
        if redirect:
            redir_link = """<p><a href="{0}">Click here to continue to your
original destination</a></p>""".format(redirect)

        redir_text = redir_wait + redir_link

        return """<div class="lg_auth_form">{redirect}</div>""".format(redirect=redir_text)
    
    @cherrypy.expose
    def new_account(self, **kwargs):
        if config['site_registration'] is None:
            return """<div class="lg_auth_form">Registration is not available for this site.</div>"""
    
        if cherrypy.request.method.upper() == 'POST':
            try:
                #check captcha
                pubkey = config['site_registration_recaptcha_publickey']
                if pubkey is not None:
                    privkey = config['site_registration_recaptcha_privatekey']
                    from recaptcha.client import captcha
                    result = captcha.submit(
                        kwargs['recaptcha_challenge_field']
                        ,kwargs['recaptcha_response_field']
                        ,privkey
                        ,cherrypy.request.remote.ip
                        )
                    log('Recaptcha verification: ' + str(result.is_valid))
                    if not result.is_valid:
                        raise AuthError(result.error_code)

                uname = kwargs['username']
                uargs = { 'groups': [] }
                ok = True
                if 'password' in kwargs:
                    if kwargs['password'] != kwargs['password2']:
                        kwargs['error'] = 'Passwords did not match'
                        ok = False
                    uargs['auth_password'] = {
                        'date': datetime.datetime.utcnow()
                        ,'pass': [ 'sha256', passwords.sha256(kwargs['password']) ]
                        }
                
                if kwargs.get('openid', '') == 'stored':
                    uargs['auth_openid'] = [ cherrypy.session['openid_url'] ]
                
                if ok:
                    if config['site_registration'] != 'open':
                        config.auth.user_create_holder(uname, uargs)
                        #TODO - Registration forward
                    else:
                        config.auth.user_create(uname, uargs)
                    raise cherrypy.HTTPRedirect(
                        url_add_parms(
                            'new_account_ok'
                            , { 'redirect': kwargs.get('redirect', '') }
                            )
                        )
            except AuthError as e:
                kwargs['error'] = e

        template_args = { 
            'openid': kwargs.get('openid', '') 
            ,'password_form': ''
            ,'error': kwargs.get('error', '')
            ,'username': kwargs.get('username', '')
            ,'redirect': kwargs.get('redirect', '')
            }
        if kwargs.get('openid') != 'stored':
            template_args['password_form'] = """
<tr><td>Password</td><td><input type="password" name="password" /></td></tr>
<tr><td>Password (again)</td><td><input type="password" name="password2" /></td></tr>
"""

        #TODO - Go through registration providers, and ask for fields
        reg_forms = []
        template_args['registration_forms'] = ''.join(reg_forms)
        
        #Captcha form
        template_args['captcha_form'] = ''
        pubkey = config['site_registration_recaptcha_publickey']
        if pubkey is not None:
            from recaptcha.client import captcha
            template_args['captcha_form'] = """<tr><td colspan="2">{captcha}</td></tr>""".format(captcha=captcha.displayhtml(pubkey))

        return """<div class="lg_auth_form lg_auth_new_account">
<span style="color:#ff0000;" class="lg_auth_error">{error}</span>
<form method="POST" action="new_account">
  <h1>New User Registration</h1>
  <input type="hidden" name="redirect" value="{redirect}" />
  <input type="hidden" name="openid" value="{openid}" />
  <table>
    <tr><td>Username</td><td><input type="text" name="username" value="{username}" /></td></tr>
    {password_form}
    {registration_forms}
    {captcha_form}
    <tr><td><input type="submit" value="Submit" /></td></tr>
  </table>
</form>
</div>""".format(**template_args)

    @cherrypy.expose
    @groups('auth')
    def change_password(self, **kwargs):
        error = ''
        if 'oldpass' in kwargs:
            if not config.auth.test_password(cherrypy.user.name, kwargs['oldpass']):
                error = 'Incorrect password'
            elif kwargs['newpass'] != kwargs['newpass2']:
                error = 'New passwords do not match'
            else:
                new_pass = kwargs['newpass']
                if len(new_pass) < 6:
                    error = 'Password must be 6 or more characters'
                else:
                    config.auth.set_user_password(
                        cherrypy.user.name
                        , [ 'sha256', passwords.sha256(new_pass) ]
                        )
                    return "Password changed successfully."
        return """
<div class="lg_auth_form">
<span style="color:#ff0000;" class="lg_auth_error">{error}</span>
<form action="change_password" method="POST">
  <p>
    Change Password:
    <table>
      <tr><td>Old Password</td><td><input type="password" name="oldpass" /></td></tr>
      <tr><td>New Password</td><td><input type="password" name="newpass" /></td></tr>
      <tr><td>New Password (again)</td><td><input type="password" name="newpass2" /></td></tr>
      <tr><td><input type="submit" value="Submit" /></td></tr>
    </table>
  </p>
</form>
</div>
        """.format(error=error)

    @cherrypy.expose
    @method_filter(methods=['POST'])
    def login_password(self, username, password, redirect=None):
        if config.auth.test_password(username, password):
            user = config.auth.login(username)
            self.login_redirect(user, redirect)
        raise cherrypy.HTTPRedirect(
            url_add_parms(
                'login'
                , { 'error': 'Invalid Credentials', 'redirect': redirect or '' }
                )
            )

    def login_openid_response(self, url, redirect=None, **kwargs):
        """Handles an openid login.  
        This is called directly by a descendent of the AuthRoot path.
        """
        username = config.auth.get_user_from_openid(url)
        if username is not None:
            user = config.auth.login(username)
            self.login_redirect(user, redirect)

        #No known user has that openID... ask if they want to register,
        #if applicable.
        if config['site_registration'] is None:
            raise cherrypy.HTTPRedirect(
                url_add_parms('../login', { 'error': 'Unknown OpenID: ' + url, 'redirect': redirect or '' })
                )
        else:
            #We store the openid in session to prevent abusive services
            #registering a bunch of usernames with OpenID urls that do
            #not belong to them.
            cherrypy.session['openid_url'] = url
            raise cherrypy.HTTPRedirect(
                url_add_parms('../new_account', { 'error': 'Unknown OpenID.  If you would like to register an account with this OpenID, fill out the following form:', 'openid': 'stored', 'redirect': redirect or '' })
                )

