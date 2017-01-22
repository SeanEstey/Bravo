from re import match, search

re_blck = r'(B|R)\d{1,2}\w'
re_bus_blck = r'B\d{1,2}[A-E]{1}'
re_res_blck = r'R\d{1,2}[a-zA-Z]{1}'
re_postal = r'T\d[A-Z]\s?(\d[A-Z]\d)?'
re_acct_id = r'[\/]?\d{1,6}'

def is_block(s):
    return match('^%s$' % re_blck, s) is not None

def get_block(title):
    m = search(re_blck, title)
    return m.group(0) if m else False

def is_res(block):
    return match('^%s$' % re_res_blck, block) is not None

def is_bus(block):
    return match('^%s$' % re_bus_blck, block) is not None

def block_to_rmv(s):
    m = search(r'\*{3}RMV\s%s(.+)?\*{3}' % re_blck, s)
    if not m: return False
    return search(re_blck, m.group(0)).group(0)

def is_block_list(s):
    return match(r'^(,?\s*' + re_blck + r')*$', s) is not None

def is_postal_code(s):
    return match(r'^%s$' % re_postal, s) is not None

def has_postal(s):
    return search(re_postal, s) is not None

def is_account_id(s):
    return match(r'^%s$' % re_acct_id, s) is not None

def get_num_booked(event_summary):
    m = search(r'\(\d{1,3}\/', event_summary)
    if not m: return False
    return m.group(0)[1:-1]

def get_area(evnt_sumry):
    m = search(r'\[(.*)\]', evnt_sumry)
    if not m: return False
    return m.group(0)[1:-1]
