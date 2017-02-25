'''app.routing.sheet'''
import logging, re, time
from .. import get_logger, get_keys
from app.lib import gdrive, gsheets
from app.main.parser import has_postal
log = get_logger('routing.sheet')

#-------------------------------------------------------------------------------
def build(agcy, drive_api, title):
    '''Makes copy of Route Template, add edit/owner permissions
    IMPORTANT: Make sure 'Routed' folder has edit permissions for agency
    service account.
    IMPORTANT: Make sure route template file has edit permissions for agency
    service account.
    Uses batch request for creating permissions
    Returns: new Sheet file
    '''

    # Copy Route Template

    gdrive_conf = get_keys('routing',agcy=agcy)['gdrive']
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
def write_orders(sheets_api, ss_id, orders):
    '''Write formatted orders to route sheet.'''

    log.debug('writing %s orders', len(orders))

    rows = []
    bold_rng = []
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
                bold_rng.append([idx+1+1, 4])
                summary += 'NOTE: ' + notes['driver notes'] +'\n\n'
                if notes['driver notes'].find('***') > -1:
                    summary = summary.replace("***", "")
            summary += 'Name: ' + notes['name'] + '\n'
            if notes.get('neighborhood'):
              summary += 'Neighborhood: ' + notes['neighborhood'] + '\n'
            summary += 'Block: ' + notes['block']
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
        gsheets.write_rows(sheets_api, ss_id, range_, rows)
        gsheets.vert_align_cells(sheets_api, ss_id, 2, len(orders)+1, 1,1)
        gsheets.bold_cells(sheets_api, ss_id, bold_rng)
        values = gsheets.get_values(sheets_api, ss_id, 'Route', 'A1:$A')
        marker = '***Route Info***'
        n_rows = gsheets.num_rows(sheets_api, ss_id, 'Route')
        hide_end = values.index([marker]) if [marker] in values else n_rows
        gsheets.hide_rows(
            sheets_api,
            ss_id,
            1 + len(rows) + 1,
            hide_end)
    except Exception as e:
        log.error('sheets error: %s', str(e))
        raise

#-------------------------------------------------------------------------------
def write_order(sheets_api, ss_id, order, row):
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
    summary += 'Block: %s'% notes['block']
    if notes.get('contact'):
      summary += '\nContact: ' + notes['contact']
    if notes.get('phone'):
      summary += '\nPhone: ' + notes['phone']
    if notes.get('email'):
      summary += '\nEmail: ' + notes['email']

    log.debug('writing order. summary=%s, loc_name=%s, gmaps_url=%s, notes[id]=%s',
        summary, order['gmaps_url'], order['location']['name'], notes['id'])

    gsheets.write_rows(
        sheets_api,
        ss_id,
        'Route!' + str(row)+":"+str(row),
        [[
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
        ]])


#-------------------------------------------------------------------------------
def append_order(sheets_api, ss_id, order):
    '''@order: dict returned from routific.order():
    '''

    values = gsheets.get_values(sheets_api, ss_id, 'Route', "E1:$E")
    insert_idx = None

    for i in range(0, len(values)):
        if values[i][0] == 'depot':
            insert_idx = i

    gsheets.insert_rows_above(sheets_api, ss_id, insert_idx+1, 1)
    write_order(sheets_api, ss_id, order, insert_idx+1)
