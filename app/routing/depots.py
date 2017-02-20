'''app.routing.depots'''
import logging
from app import get_logger, get_keys
log = get_logger('routing.depots')

#-------------------------------------------------------------------------------
def resolve(block, postal_codes, event_desc=False):
    '''Find correct depot for given Block.
    First see if 'routing.depots' has defined this Block belongs to it.
    Next see if Google Cal Event Desc defines a depot.
    Last, see if 'routing.depots' postal_codes match ones given.
    Return 'Strathcona' as default if none found.
    '''

    agcy = 'wsf'

    depots = list(get_keys('routing',agcy=agcy)['locations']['depots'])

    for depot in depots:
        # The block defined under depot in list?
        if depot.get('blocks') and block in depot['blocks']:
            return depot

        # Depot defined in Calendar Event desc?
        if event_desc and event_desc.find(depot['name']) > -1:
            return depot

    # Depot not explicitly defined.
    # Do postal code lookup
    for depot in depots:
        if not depot.get('postal_codes'):
            continue

        if set(depot['postal_codes']) & set(postal_codes):
            return depot

    # Still haven't found depot. Use Strathcona as default
    log.error(
        'No depot defined for Block %s. '\
        'Postal codes: [%s]. Using Strathcona as default.',
        block, postal_codes)

    for depot in depots:
        if depot['name'] == 'Strathcona':
            return depot
