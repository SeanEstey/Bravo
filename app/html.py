
# TODO: rename all "render_html" calls to "html.render". Is this function even still used???
# TODO: rename all "print_html" calls to "to_list_tags"
# TODO: rename all " dict_to_html_table" to "to_table"
# TODO: rename all "clean_html" to "clean_whitespace"


#-------------------------------------------------------------------------------
def render(template, data, flask_context=False):
    '''Passes JSON data to views._render_html() context. Returns
    html text'''

    data = json.loads(json_util.dumps(data))
    data = json.loads(bson_date_fixer(data))

    logger.debug('rendering_html for dict: %s', data)
    logger.debug('render template: %s', template)

    if flask_context == False:
        try:
            response = requests.post(
              app.config['LOCAL_URL'] + '/render_html',
              json={
                  "template": template,
                  "data": data
              })
        except requests.RequestException as e:
            logger.error('render_template: %s', str(e))
            return False
    else:
        logger.debug('we have flask context. calling render_template directly')

        try:
            return flask.render_template(
                template,
                account = data.get('account') or None,
                call = data.get('call') or None)
        except Exception as e:
            logger.error('render_html: %s ', str(e))
            return 'Error'

    return response.text
    
#-------------------------------------------------------------------------------
def to_list_tags(dictObj):
  p='<ul style="list-style-type: none;">'
  for k,v in dictObj.iteritems():
    if isinstance(v, dict):
      p+='<li>'+ to_title_case(k)+': '+print_html(v)+'</li>'
    elif isinstance(v, list):
      p+='<br><li><b>'+to_title_case(k)+': </b></li>'
      p+='<ul style="list-style-type: none;">'
      for idx, item in enumerate(v):
        p+='<li>['+str(idx+1)+']'+print_html(item)+'</li>'
      p+='</ul>'
    else:
      p+='<li>'+ to_title_case(k)+ ': '+ remove_quotes(json_util.dumps(v)) + '</li>'
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
            p+= '<td nowrap>' + indent + to_title_case(k) + ':    ' + str(v) + '</td>'
            #p+= '<td>' + str(v) + '</td>'
            p+= '</tr>'

        elif isinstance(v, dict):
            p+='<tr><td nowrap>' + h_open + indent + to_title_case(k) + h_close + '</td></tr>'
            p+='<tr><td>'+ dict_to_html_table(v, depth+1)+'</td></tr>'

        elif isinstance(v, list):
            p+='<tr><td nowrap>' + h_open + indent + to_title_case(k) + h_close + '</td></tr>'

            for idx, item in enumerate(v):
                p+='<tr><td>'+ dict_to_html_table(item, depth+1)+'</td></tr>'

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
