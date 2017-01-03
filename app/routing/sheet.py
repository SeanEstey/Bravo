'''app.routing.sheet'''

import logging
from time import sleep
import re

from app import db
from .. import gsheets, gdrive, utils

logger = logging.getLogger(__name__)

#-------------------------------------------------------------------------------
def build(agency, drive_api, title):
    '''Makes copy of Route Template, add edit/owner permissions
    IMPORTANT: Make sure 'Routed' folder has edit permissions for agency
    service account.
    IMPORTANT: Make sure route template file has edit permissions for agency
    service account.
    Uses batch request for creating permissions
    Returns: new Sheet file
    '''

    conf = db.agencies.find_one({'name':agency})['routing']['gdrive']

    # Copy Route Template
    file_copy = drive_api.files().copy(
      fileId = conf['template_sheet_id'],
      body = {
        'name': title,
        'parents': [conf['routed_folder_id']]
      }
    ).execute()

    # Prevent 500 errors
    sleep(2)

    # Transfer ownership permission, add writer permissions
    gdrive.add_permissions(drive_api, file_copy['id'], conf['permissions'])

    logger.debug('Permissions added')

    _file = drive_api.files().get(
        fileId=file_copy['id'],
        fields='*'
    ).execute()

    #logger.debug(utils.print_vars(_file, depth=5))

    logger.debug('sheet_id %s created', file_copy['id'])

    return _file



#-------------------------------------------------------------------------------
def write_orders(sheets_api, ss_id, orders):
    '''Write formatted orders to route sheet.'''

    rows = []
    cells_to_bold = []

    # Chop off office start_address
    orders = orders[1:]

    for idx in range(len(orders)):
        order = orders[idx]

        addy = order['location_name'].split(', ')

        # Remove Postal Code from Google Maps URL label
        if re.match(r'^T\d[A-Z]$', addy[-1]) or re.match(r'^T\d[A-Z]\s\d[A-Z]\d$', addy[-1]):
           addy.pop()

        formula = '=HYPERLINK("' + order['gmaps_url'] + '","' + ", ".join(addy) + '")'

        '''Info Column format (column D):

        Notes: Fri Apr 22 2016: Pickup Needed
        Name: Cindy Borsje

        Neighborhood: Lee Ridge
        Block: R10Q,R8R
        Contact (business only): James Schmidt
        Phone: 780-123-4567
        Email: Yes/No'''

        order_info = ''

        if order['location_id'] == 'depot':
            order_info += 'Name: Depot\n'
            order_info += '\nArrive: ' + order['arrival_time']
        elif order['location_id'] == 'office':
            order_info += 'Name: ' + order['customNotes']['name']+ '\n'
            order_info += '\nArrive: ' + order['arrival_time']
        # Regular order
        else:
            if order['customNotes'].get('driver notes'):
                # Row = (order idx + 1) + 1 (header)
                cells_to_bold.append([idx+1+1, 4])

                order_info += 'NOTE: ' + order['customNotes']['driver notes'] +'\n\n'

                if order['customNotes']['driver notes'].find('***') > -1:
                    order_info = order_info.replace("***", "")

            order_info += 'Name: ' + order['customNotes']['name'] + '\n'

            if order['customNotes'].get('neighborhood'):
              order_info += 'Neighborhood: ' + order['customNotes']['neighborhood'] + '\n'

            order_info += 'Block: ' + order['customNotes']['block']

            if order['customNotes'].get('contact'):
              order_info += '\nContact: ' + order['customNotes']['contact']
            if order['customNotes'].get('phone'):
              order_info += '\nPhone: ' + order['customNotes']['phone']
            if order['customNotes'].get('email'):
              order_info += '\nEmail: ' + order['customNotes']['email']

            order_info += '\nArrive: ' + order['arrival_time']

        rows.append([
          formula,
          '',
          '',
          order_info,
          order['customNotes'].get('id') or '',
          order['customNotes'].get('driver notes') or '',
          order['customNotes'].get('block') or '',
          order['customNotes'].get('neighborhood') or '',
          order['customNotes'].get('status') or '',
          order['customNotes'].get('office notes') or ''
        ])

    # Start from Row 2 Column A to Column J
    _range = "A2:J" + str(len(orders)+1)

    try:
        gsheets.write_rows(sheets_api, ss_id, rows, _range)
        gsheets.vert_align_cells(sheets_api, ss_id, 2, len(orders)+1, 1,1)
        gsheets.bold_cells(sheets_api, ss_id, cells_to_bold)

        values = gsheets.get_values(sheets_api, ss_id, "A1:$A")

        hide_start = 1 + len(rows) + 1;
        hide_end = values.index(['***Route Info***'])

        gsheets.hide_rows(sheets_api, ss_id, hide_start, hide_end)
    except Exception as e:
        logger.error('sheets error: %s', str(e))

#-------------------------------------------------------------------------------
def write_order(sheets_api, ss_id, order, row):
    '''Write single order to empty row on Sheet
    TODO: doesn't add Bold formatting yet.'''

    order_info = ''

    if order['customNotes'].get('driver notes'):
        # Row = (order idx + 1) + 1 (header)
        #cells_to_bold.append([idx+1+1, 4])

        order_info += 'NOTE: ' + order['customNotes']['driver notes'] +'\n\n'

        if order['customNotes']['driver notes'].find('***') > -1:
            order_info = order_info.replace("***", "")

    order_info += 'Name: ' + order['customNotes']['name'] + '\n'

    if order['customNotes'].get('neighborhood'):
      order_info += 'Neighborhood: ' + order['customNotes']['neighborhood'] + '\n'

    order_info += 'Block: ' + order['customNotes']['block']

    if order['customNotes'].get('contact'):
      order_info += '\nContact: ' + order['customNotes']['contact']
    if order['customNotes'].get('phone'):
      order_info += '\nPhone: ' + order['customNotes']['phone']
    if order['customNotes'].get('email'):
      order_info += '\nEmail: ' + order['customNotes']['email']

    #order_info += '\nArrive: ' + order['arrival_time']

    logger.debug(order_info)

    gsheets.write_rows(
        sheets_api,
        ss_id,
        [[
            '=HYPERLINK("' + order['gmaps_url'] + '","' + order['location']['name'] + '")',
            '',
            '',
            order_info,
            order['customNotes']['id'],
            order['customNotes']['driver notes'],
            order['customNotes']['block'],
            order['customNotes']['neighborhood'],
            order['customNotes']['status'],
            order['customNotes']['office notes']
        ]],
        str(row)+":"+str(row)
    )

    return True

#-------------------------------------------------------------------------------
def append_order(sheets_api, ss_id, order):
    '''@order: dict returned from routific.order():
    '''

    values = gsheets.get_values(sheets_api, ss_id, "E1:$E")

    insert_idx = None

    for i in range(len(values)):
        if values[i][0] == 'depot':
            insert_idx = i

    logger.info('insert row at idx %s', insert_idx)

    gsheets.insert_rows_above(sheets_api, ss_id, insert_idx+1, 1)

    #from time import sleep
    #sleep(2)

    write_order(sheets_api, ss_id, order, insert_idx+1)

    return True
