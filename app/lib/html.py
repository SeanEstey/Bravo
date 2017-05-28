'''app.lib.html'''
import re
from bson import json_util
from . import utils

def title_case(s):
    s = re.sub(r'\"', '', s)
    s = re.sub(r'_', ' ', s)
    return s.title()

def rmv_quotes(s):
    s = re.sub(r'\"', '', s)
    return s

#-------------------------------------------------------------------------------
def to_list_tags(dictObj):
  p='<ul style="list-style-type: none;">'
  for k,v in dictObj.iteritems():
    if isinstance(v, dict):
      p+='<li>'+ title_case(k)+': '+ to_list_tags(v) +'</li>'
    elif isinstance(v, list):
      p+='<br><li><b>'+ title_case(k) +': </b></li>'
      p+='<ul style="list-style-type: none;">'
      for idx, item in enumerate(v):
        p+='<li>['+str(idx+1)+']' + to_list_tags(item) + '</li>'
      p+='</ul>'
    else:
      p+='<li>'+ title_case(k)+ ': '+ rmv_quotes(json_util.dumps(v)) + '</li>'
  p+='</ul>'
  return p

#-------------------------------------------------------------------------------
def to_div(k, v, depth=None):
    indent = ''

    if depth is None:
        depth = 0

    h_open = '<h4>'
    h_close = '</h4>'

    p=''

    if isinstance(v, dict):
        p+= '<div name="'+str(k)+'">'

        if type(k) is str or type(k) is unicode:
            p+= '<label style="margin-left:'+str(depth)+'em">' + h_open + title_case(str(k)) + h_close + '</label>'

        for sub_k, sub_v in v.iteritems():
            p+= to_div(sub_k, sub_v, depth+1)

        p+= '</div>'
    elif isinstance(v, list):
        p+= '<div name="'+k+'">'

        if type(k) is str or type(k) is unicode:
            p+= '<label style="margin-left:'+str(depth)+'em">' + h_open + title_case(k) + h_close + '</label>'

        for idx, item in enumerate(v):
            #p+= '<div name="'+str(idx)+'">' + to_div(idx, item, depth+1) + '</div>'
            p+= to_div(idx, item, depth+1)

        p+= '</div>'
    elif type(v) is float or type(v) is int or type(v) is str or type(v) is unicode:
        p+= '<div name="'+str(k)+'">'

        p+= '<label style="display:inline-block; margin-right:0.25em; margin-left:'+str(depth)+'em">' + title_case(str(k)) + ':</label>'

        if type(v) == int:
            _type= "number"
        else:
            _type = "text"

        p+= '<input class="input" type="'+_type+'" style="display:inline-block;" value="'+str(v)+'"></input>'
        p+= '</div>'

    return p

#-------------------------------------------------------------------------------
def clean_whitespace(raw_html):
    '''Strips out all HTML tags, line breaks, and extra whitespace from string'''

    no_lines = re.sub(r'\r|\n', '', raw_html)
    no_tags = re.sub(r'<.*?>', '', no_lines)

    # Remove extra spaces between any charater boundaries
    no_ws = re.sub(r'(\b|\B)\s{2,}(\b|\B)', ' ', no_tags)

    return no_ws.rstrip().lstrip()
