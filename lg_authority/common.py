
import cherrypy

class ConfigDict(dict):
    """Holds all configuration items.  Its own class so that
    it may hold flags as well.
    """

config = ConfigDict()
#Set defaults, show params.  These are overwritten first 
#by any config in the tools.lg_authority or lg_authority section, then
#CherryPy config.
config.update({
    'site_key': 'abc123o2qh3otin;oiH#*@(TY(#*Th:T*:(@#HTntb982#HN(:@#*TBH:@#(*THioihI#HOIH%oihio3@H%IOH#@%I)(!*@Y%+(+!@H%~`un23gkh'
    #Site encryption key for passwords.  Should be more than 60 chars.
    ,
    'user_slate_prefix': 'user-'
    #The prefix for named slates for each user (only applicable when using
    #lamegame_cherrypy_slates
    ,
    'authtype': 'userlist'
    #type of system that users and groups are fetched from
    ,
    'authtype_conf': {
        'users': {
            #The example admin user - the password is 'admin', and
            #was processed through lg_authority.passwords.sha256('admin').
            #These hashes may also be generated through 
            #AuthRoot()/helper/sha256
            'admin': {
                'auth': { 'password': ( 'sha256', ['bff74028f285748241375d1c9c7f9b6e85fd3900edf8e601a78f7f84d848b42e', 'admin'] ) }
                ,'groups': [ 'admin' ]
                }
            }
        }
    #Configuration options for the user/group store
    ,
    'groups': [ 'any' ]
    #Static groups allowed to access the resource.  If the FIRST ELEMENT
    #of the array is 'all:', then the user must be in EVERY group specified
    #to gain access.  Otherwise, if the user matches a single group, they
    #will be allowed access.  This convention is ugly, but prevents errors
    #when a site might wish to use both AND and OR group configurations
    #in the same environment.
    #'any' means everyone, even unauthenticated users
    #'auth' means all authenticated users
    #'user-' + username means specifically username
    ,
    'user_home_page': '/'
    #The page to redirect to (if relative, then from AuthRoot/OneLevel/)
    #on successful authentication when a redirect action was not requested.
    #May be a function that returns a URL, given a user record.
    ,
    'logout_page': None
    #Page to redirect to on logout.  Use None to show a standard auth
    #page confirming the logout.
    ,
    'deny_page_anon': '/auth/login'
    #Page that unauthorized users are sent to when trying to access a
    #resource they cannot retrieve AND are not authenticated.  
    #Use None for a standard "Access Denied" page.
    #
    #deny_page_anon may be pointed to a login page.
    ,
    'deny_page_auth': None
    #Page that unauthorized users are sent to when trying to access a
    #resource they cannot retrieve AND are already authenticated.
    #Use None for a standard "Access Denied" page.
    })

#Commonly resolve urlencode
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

def url_add_parms(base, qs):
    if type(qs) != dict:
        raise TypeError('qs must be dict')
    if len(qs) == 0:
        return base
    qs = urlencode(qs)
    if '?' in base:
        return base + '&' + qs
    return base + '?' + qs

# Basic rejection function calls
def deny_access():
    """Unconditionally denies access to the current request."""
    denial_key = 'deny_page_anon'
    if cherrypy.serving.user is not None:
        denial_key = 'deny_page_auth'

    denial = cherrypy.tools.lg_authority._merged_args()[denial_key]
    if denial is not None:
        raise cherrypy.HTTPRedirect(
            url_add_parms(denial, { 'redirect': cherrypy.url(relative='server', qs=cherrypy.request.query_string) })
            )
    else:                
        raise cherrypy.HTTPError(401, 'Access Denied')

def groups(*groups):
    """Decorator function that winds up calling cherrypy.config(**{ 'tools.lg_authority.groups': groups })"""
    return cherrypy.config(**{ 'tools.lg_authority.groups': groups })

def check_groups(*groups):
    """Compare the user's groups to *groups.  If the user is in ANY
    of the supplied groups, access is granted.  Otherwise, an
    appropriate cherrypy.HTTPRedirect or cherrypy.HTTPError is raised.
    """
    if len(groups) == 1 and type(groups[0]) == list:
        raise TypeError('You passed a list to check_groups.  Instead pass *list.')
    user = cherrypy.serving.user

    allow = False
    if 'any' in groups:
        allow = True
    elif user is not None:
        if 'auth' in groups:
            allow = True
        else:
            usergroups = user['groups']
            for group in groups:
                if group in usergroups:
                    allow = True
                    break

    if not allow:
        deny_access()

def check_groups_all(*groups):
    """Compare the user's groups to *groups.  If the user is in ALL
    of the supplied groups, access is granted.  Otherwise, an
    appropriate cherrypy.HTTPRedirect or cherrypy.HTTPError is raised.

    Passing an empty array will always allow access.
    """
    if len(groups) == 1 and type(groups[0]) == list:
        raise TypeError('You passed a list to check_groups_all.  Instead pass *list.')
    user = cherrypy.serving.user
    user_groups = [ 'any' ]
    if user is not None:
        user_groups.append('auth')
        user_groups += user.get('groups', [])

    allow = True
    for group in groups:
        if group not in user_groups:
            allow = False
            break

    if not allow:
        deny_access()

