'''app.routing.sheet'''
import re, time
from flask import g
from .. import get_keys
from app.lib import gdrive
from app.lib.gsheets_cls import SS
from app.main.parser import has_postal
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
def build(drive_api, title):
    '''Makes copy of Route Template, add edit/owner permissions
    IMPORTANT: Make sure 'Routed' folder has edit permissions for agency
    service account.
    IMPORTANT: Make sure route template file has edit permissions for agency
    service account.
    Uses batch request for creating permissions
    Returns: new Sheet file
    '''

    # Copy Route Template

    gdrive_conf = get_keys('routing')['gdrive']
    file_copy = drive_api.files().copy(
      fileId = gdrive_conf['template_sheet_id'],
      body = {
        'name': title,
        'parents': [gdrive_conf['routed_folder_id']]
      }
    ).execute()

    time.sleep(2) # Prevent 500 errors

    # Transfer ownership permission, add writer permissions

    gdrive.add_permissions(
        drive_api,
        file_copy['id'],
        gdrive_conf['permissions'])

    _file = drive_api.files().get(
        fileId=file_copy['id'],
        fields='*'
    ).execute()

    #log.debug('sheet_id %s created', file_copy['id'])
    return _file

#-------------------------------------------------------------------------------
def write_orders(wks, orders):
    '''Write formatted orders to route sheet.'''

    log.debug('writing %s orders', len(orders))

    rows = []
    blue = []
    orders = orders[1:] # Chop off office start_address

    for idx in range(len(orders)):
        order = orders[idx]
        notes = order['customNotes']
        addy = order['location_name']
        if has_postal(addy.split(', ')[-1]):
            addy = ', '.join(addy.split(', ')[0:-1])
        formula = '=HYPERLINK("%s","%s")' % (order['gmaps_url'],addy)
        summary = ''
        if order['location_id'] == 'depot':
            summary += 'Name: Depot\n'
            summary += '\nArrive: ' + order['arrival_time']
        elif order['location_id'] == 'office':
            summary += 'Name: ' + notes['name']+ '\n'
            summary += '\nArrive: ' + order['arrival_time']
        else:
            if notes.get('driver notes'):
                summary += 'NOTE: ' + notes['driver notes'] +'\n\n'
                if notes['driver notes'].find('***') > -1:
                    summary = summary.replace("***", "")

            if notes.get('status') == 'Dropoff':
                blue.append([idx+1+1, 4])

            summary += 'Name: ' + notes['name'] + '\n'
            if notes.get('neighborhood'):
              summary += 'Neighborhood: ' + notes['neighborhood'] + '\n'
            #summary += 'Block: ' + notes['block']
            if notes.get('contact'):
              summary += '\nContact: ' + notes['contact']
            if notes.get('phone'):
              summary += '\nPhone: ' + notes['phone']
            if notes.get('email'):
              summary += '\nEmail: ' + notes['email']
            summary += '\nArrive: ' + order['arrival_time']

        rows.append([
          formula,
          '',
          '',
          summary,
          notes.get('id') or '',
          notes.get('driver notes') or '',
          notes.get('block') or '',
          notes.get('neighborhood') or '',
          notes.get('status') or '',
          notes.get('office notes') or ''
        ])

    # Start from Row 2 Column A to Column J
    range_ = "A2:J" + str(len(orders)+1)

    try:
        wks.appendRows(rows)
        wks.textFormat({'foregroundColor':{'red':0.5,'green':0.5,'blue':1.0,'alpha':1.0}}, blue)
    except Exception as e:
        log.exception('Error writing orders: %s', e.message)
        raise

#-------------------------------------------------------------------------------
def write_order(wks, order, row):
    '''Write single order to empty row on Sheet
    TODO: doesn't add Bold formatting yet.'''

    notes = order['customNotes']
    summary = ''
    if notes.get('driver notes'):
        summary += 'NOTE: %s\n\n'% notes['driver notes']
        if notes['driver notes'].find('***') > -1:
            summary = summary.replace("***", "")
    summary += 'Name: %s\n'% notes['name']
    if notes.get('neighborhood'):
      summary += 'Neighborhood: %s\n'% notes['neighborhood']
    #summary += 'Block: %s'% notes['block']
    if notes.get('contact'):
      summary += '\nContact: ' + notes['contact']
    if notes.get('phone'):
      summary += '\nPhone: ' + notes['phone']
    if notes.get('email'):
      summary += '\nEmail: ' + notes['email']

    log.debug('Writing order to Route Sheet', extra={
        'account_id': notes['id'],
        'order_summary': summary,
        'address': order['location']['name']})

    values = [[
        '=HYPERLINK("%s","%s")' %(
            order['gmaps_url'],order['location']['name']),
        '',
        '',
        summary,
        notes['id'],
        notes['driver notes'],
        notes['block'],
        notes['neighborhood'],
        notes['status'],
        notes['office notes']
    ]]

    wks.appendRows(values)

#-------------------------------------------------------------------------------
def write_prop(wks, route_doc):

    fields = wks.getValues('A:A')
    wks.updateCell(route_doc['date'].strftime('%A, %B %d, %Y'), row=fields.index(['Date'])+1, col=2)
    wks.updateCell(route_doc['block'], row=fields.index(['Block'])+1, col=2)
    wks.updateCell(route_doc['no_pickups'], row=fields.index(['Skips'])+1, col=2)
    wks.updateCell(route_doc['duration'], row=fields.index(['Trip Sched'])+1, col=2)

#-------------------------------------------------------------------------------
def append_order(wks, order):
    '''@order: dict returned from routific.order():
    '''

    #values = get_values(api, ss_id, wks, "E1:E")
    #insert_idx = None

    #for i in range(0, len(values)):
    #    if values[i][0] == 'depot':
    #        insert_idx = i

    write_order(wks, order, 999) # FIXME
