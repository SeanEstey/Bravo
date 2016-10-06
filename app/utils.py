import requests
import re
from bson import json_util
import json
import logging
import pytz
from datetime import datetime
import flask

from app import app, db

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def naive_to_local(dt):
    return pytz.timezone("Canada/Mountain").localize(dt, is_dst=True)

#-------------------------------------------------------------------------------
def utc_to_local(dt):
    return dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Canada/Mountain"))

#-------------------------------------------------------------------------------
def render_html(template, data, flask_context=False):
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
def bson_date_fixer(a):
    '''Convert all bson datetimes mongoDB BSON format to JSON.
    Converts timestamps to formatted date strings
    @a: dict
    '''

    try:
        a = json_util.dumps(a)

        for group in re.findall(r"\{\"\$date\": [0-9]{13}\}", a):
            timestamp = json.loads(group)['$date']/1000
            date_str = '"' + datetime.fromtimestamp(timestamp).strftime('%A, %B %d') + '"'
            a = a.replace(group, date_str)
    except Exception as e:
        logger.error('bson_to_json: %s', str(e))
        return False

    return a

#-------------------------------------------------------------------------------
def send_email(to, subject, body, conf):
    '''Send email via mailgun.
    @conf: 'mailgun' dict from 'agencies' DB
    Returns:
      -mid string on success
      -False on failure'''

    try:
        response = requests.post(
          'https://api.mailgun.net/v3/' + conf['domain'] + '/messages',
          auth=('api', conf['api_key']),
          data={
            'from': conf['from'],
            'to':  to,
            'subject': subject,
            'html': body
        })
    except requests.RequestException as e:
        logger.error('mailgun: %s ', str(e))
        return False

    logger.debug(response.text)

    return json.loads(response.text)['id']

#-------------------------------------------------------------------------------
def print_html(dictObj):
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
def dict_to_html_table(dictObj, depth=None):
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
def clean_html(raw_html):
    '''Strips out all HTML tags, line breaks, and extra whitespace from string'''

    no_lines = re.sub(r'\r|\n', '', raw_html)
    no_tags = re.sub(r'<.*?>', '', no_lines)

    # Remove extra spaces between any charater boundaries
    no_ws = re.sub(r'(\b|\B)\s{2,}(\b|\B)', ' ', no_tags)

    return no_ws.rstrip().lstrip()

#-------------------------------------------------------------------------------
def remove_quotes(s):
  s = re.sub(r'\"', '', s)
  return s

#-------------------------------------------------------------------------------
def to_title_case(s):
  s = re.sub(r'\"', '', s)
  s = re.sub(r'_', ' ', s)
  return s.title()


#-------------------------------------------------------------------------------
def dial(to, from_, twilio_keys, answer_url):
    '''Returns twilio call object'''
    import twilio
    import twilio.twiml
    
    if to[0:2] != "+1":
        to = "+1" + to

    try:
        twilio_client = twilio.rest.TwilioRestClient(
          twilio_keys['sid'],
          twilio_keys['auth_id']
        )
        
        call = twilio_client.calls.create(
          from_ = from_,
          to = to,
          url = answer_url,
          status_callback = app.config['PUB_URL'] + '/reminders/voice/on_complete',
          status_method = 'POST',
          status_events = ["completed"], # adding more status events adds cost
          method = 'POST',
          if_machine = 'Continue'
        )

        logger.debug(vars(call))

    except twilio.TwilioRestException as e:
        logger.error(e)

        if not e.msg:
            if e.code == 21216:
                e.msg = 'not_in_service'
            elif e.code == 21211:
                e.msg = 'no_number'
            elif e.code == 13224:
                e.msg = 'invalid_number'
            elif e.code == 13223:
                e.msg = 'invalid_number_format'
            else:
                e.msg = 'unknown_error'
        return e

    return call
