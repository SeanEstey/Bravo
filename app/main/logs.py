'''app.main.logs'''
from json import loads
from flask import g, request
from datetime import datetime, timedelta
from app.lib.utils import format_bson


def new_get_logs(groups=None, tags=None, levels=None):
    pass

#---------------------------------------------------------------------------
def get_logs(start=None, end=None, user=None, groups=None, tag=None, levels=None):
    '''Send log entries to client app.
    @start, end: naive datetime
    @show_levels: subset of ['debug', 'info', 'warning', 'error']
    @groups: subset of [g.group, 'sys']
    '''

    levels = []
    groups = []

    for lvl in loads(request.form['levels']):
        levels.append('DEBUG') if lvl['name'] == 'dbg_lvl' else None
        levels.append('INFO') if lvl['name'] == 'inf_lvl' else None
        levels.append('WARNING') if lvl['name'] == 'wrn_lvl' else None
        levels.append('ERROR') if lvl['name'] == 'err_lvl' else None

    for grp in loads(request.form['groups']):
        groups.append(g.group) if grp['name'] == 'usr_grp' else None
        groups.append('sys') if grp['name'] == 'sys_grp' else None
        groups.append('anon') if grp['name'] == 'anon_grp' else None

    DELTA_HRS = 24
    now = datetime.utcnow()
    start_dt = start if start else (now - timedelta(hours=DELTA_HRS))
    end_dt = end if end else now
    all_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

    logs = g.db.logs.find({
        'level': {'$in': levels} if levels else all_levels,
        'user': user or {'$exists': True},
        'group': {'$in': groups} if groups else {'$exists':True},
        'timestamp': {
           '$gte': start_dt,
           '$lt': end_dt}
        },
        {'_id':0}
    ).limit(50).sort('timestamp', -1)

    return format_bson(list(logs))
