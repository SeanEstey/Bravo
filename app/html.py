import re
from bson import json_util

from . import utils


#-------------------------------------------------------------------------------
def to_list_tags(dictObj):
  p='<ul style="list-style-type: none;">'
  for k,v in dictObj.iteritems():
    if isinstance(v, dict):
      p+='<li>'+ utils.to_title_case(k)+': '+ to_list_tags(v) +'</li>'
    elif isinstance(v, list):
      p+='<br><li><b>'+ utils.to_title_case(k) +': </b></li>'
      p+='<ul style="list-style-type: none;">'
      for idx, item in enumerate(v):
        p+='<li>['+str(idx+1)+']' + to_list_tags(item) + '</li>'
      p+='</ul>'
    else:
      p+='<li>'+ utils.to_title_case(k)+ ': '+ utils.remove_quotes(json_util.dumps(v)) + '</li>'
  p+='</ul>'
  return p


#-------------------------------------------------------------------------------
def to_table(dictObj, depth=None):
    indent = ''

    if depth is not None:
        for i in range(depth):
            indent += '&nbsp;&nbsp;&nbsp;&nbsp;'
    else:
        depth = 0

    h_open = '<h4>'
    h_close = '</h4>'

    p='<table>'

    for k,v in dictObj.iteritems():
        if type(v) is float or type(v) is int or type(v) is str or type(v) is unicode:
            p+= '<tr>'
            p+= '<td nowrap>' + indent + utils.to_title_case(k) + ':    ' + str(v) + '</td>'
            #p+= '<td>' + str(v) + '</td>'
            p+= '</tr>'

        elif isinstance(v, dict):
            p+='<tr><td nowrap>' + h_open + indent + utils.to_title_case(k) + h_close + '</td></tr>'
            p+='<tr><td>'+ to_table(v, depth+1) + '</td></tr>'

        elif isinstance(v, list):
            p+='<tr><td nowrap>' + h_open + indent + utils.to_title_case(k) + h_close + '</td></tr>'

            for idx, item in enumerate(v):
                p+='<tr><td>'+ to_table(item, depth+1) + '</td></tr>'

    p+='</table>'

    return p

#-------------------------------------------------------------------------------
def clean_whitespace(raw_html):
    '''Strips out all HTML tags, line breaks, and extra whitespace from string'''

    no_lines = re.sub(r'\r|\n', '', raw_html)
    no_tags = re.sub(r'<.*?>', '', no_lines)

    # Remove extra spaces between any charater boundaries
    no_ws = re.sub(r'(\b|\B)\s{2,}(\b|\B)', ' ', no_tags)

    return no_ws.rstrip().lstrip()
