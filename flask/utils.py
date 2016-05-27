from config import *
import requests
import re
from bson import json_util
import json


def has_bounced(address):
  send_url = 'https://api.mailgun.net/v3/' + MAILGUN_DOMAIN + '/bounces'
  r = requests.get(
    send_url + '/' + address, 
    auth=('api', MAILGUN_API_KEY)
  )
  
  r = json.loads(r.content)
  
  if 'bounce' in r:
    return True
  else:
    return False

def get_today_fails():
  from email.Utils import formatdate
  import time
  import datetime
  #fire_dtime = db['jobs'].find({'_id':id})
  fire_dtime = datetime.datetime.now()
  timetuple = fire_dtime.timetuple()
  stamp = time.mktime(timetuple) - 10000

  send_url = 'https://api.mailgun.net/v3/' + MAILGUN_DOMAIN + '/events'
  return requests.get(
    send_url,
    auth=('api', MAILGUN_API_KEY),
    params={
      'event' : 'rejected OR failed',
      'begin' : formatdate(stamp),
      'ascending' : 'yes'
    }
  )


def send_mailgun_email(recipients, subject, msg):
  send_url = 'https://api.mailgun.net/v3/' + MAILGUN_DOMAIN + '/messages'
  return requests.post(
    send_url,
    auth=('api', MAILGUN_API_KEY),
    data={
      'from': FROM_EMAIL,
      'to': recipients,
      'subject': subject,
      'html': msg
  })

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

def dict_to_html_table(dictObj):
  p='<table>'
  for k,v in dictObj.iteritems():
    if isinstance(v, dict):
      p+='<td>'+ dict_to_html_table(v)+'</td>'
    elif isinstance(v, list):
      #p+='<br><li><b>'+to_title_case(k)+': </b></li>'
      #p+='<ul style="list-style-type: none;">'
      for idx, item in enumerate(v):
        p+='<tr>'+dict_to_html_table(item)+'</tr>'
      #p+='</ul>'
    else:
      p+='<td>'+ remove_quotes(json_util.dumps(v)) + '</td>'
  p+='</table>'
  return p

def remove_quotes(s):
  s = re.sub(r'\"', '', s)
  return s

def to_title_case(s):
  s = re.sub(r'\"', '', s)
  s = re.sub(r'_', ' ', s)
  return s.title()
