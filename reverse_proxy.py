import os
import bravo

'''Wrap the application in this middleware and configure the 
front-end server to add these headers, to let you quietly bind 
this to a URL other than / and to an HTTP scheme that is 
different than what is used locally
'''
class ReverseProxied(object):
  def __init__(self, app):
    self.app = app
    self.public_url = ''

  def __call__(self, environ, start_response):
    scheme = environ.get('HTTP_X_SCHEME', '')
    script_name = environ.get('HTTP_X_SCRIPT_NAME', '')

    if script_name:
      environ['SCRIPT_NAME'] = script_name
      path_info = environ['PATH_INFO']
      if path_info.startswith(script_name):
        environ['PATH_INFO'] = path_info[len(script_name):]

    if scheme:
      environ['wsgi.url_scheme'] = scheme

    full_url = scheme + '://' + environ['HTTP_HOST'] + script_name
    if full_url.find('localhost') < 0:
      os.environ['PUB_URL'] = full_url
      print 'ReverseProxied called! ' + os.environ['PUB_URL']

    return self.app(environ, start_response)

  def getPublicUrl(self):
    return self.public_url
