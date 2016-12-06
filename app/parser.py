import re

block_regex = r'(B|R)\d{1,2}[a-zA-Z]{1}'
bus_block_regex = r'B\d{1,2}[A-E]{1}'
res_block_regex = r'R\d{1,2}[a-zA-Z]{1}'
postal_code_regex = r'T\d[A-Z]\s?(\d[A-Z]\d)?'
account_id_regex = r'[\/]?\d{1,6}'

#-------------------------------------------------------------------------------
def is_block(s):
    return re.match('^' + block_regex + '$', s) is not None

#-------------------------------------------------------------------------------
def get_block(title):
    r = re.search(block_regex, title)

    if r:
        return r.group(0)
    else:
        return False

#-------------------------------------------------------------------------------
def is_res(block):
    return re.match('^' + res_block_regex + '$', block) is not None

#-------------------------------------------------------------------------------
def is_bus(block):
    return re.match('^' + bus_block_regex + '$', block) is not None

#-------------------------------------------------------------------------------
def block_to_rmv(s):
    r = re.search(r'\*{3}RMV\s' + block_regex + r'\*{3}', s)

    if r:
        return re.search(block_regex, r.group(0)).group(0)
    else:
        return False

#-------------------------------------------------------------------------------
def is_block_list(s):
    # Comma-separated list of blocks: 'B4A, R2M, R5S'
    return re.match(r'^(,?\s*' + block_regex + r')*$', s) is not None

#-------------------------------------------------------------------------------
def is_postal_code(s):
    return re.match(r'^' + postal_code_regex + r'$', s) is not None

#-------------------------------------------------------------------------------
def is_account_id(s):
    return re.match(r'^' + account_id_regex + r'$', s) is not None

#-------------------------------------------------------------------------------
def get_num_booked(event_summary):
    booked_re = r'\(\d{1,3}\/'
    if re.search(booked_re, event_summary):
        return re.search(booked_re, event_summary).group(0)[1:-1]
    else:
        return False

#-------------------------------------------------------------------------------
def get_area(event_summary):
    area_re = r'\[(.*)\]'

    if re.search(area_re, event_summary):
        return re.search(area_re, event_summary).group(0)[1:-1]
    else:
        return False
