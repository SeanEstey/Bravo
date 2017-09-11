'''app.routing.views'''
from flask import g, render_template
from flask_login import login_required
from .. import get_keys
from . import routing
from .main import get_metadata
from .tasks import discover_routes
from logging import getLogger
log = getLogger(__name__)

#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():

    discover_routes.delay(g.group)

    return render_template(
        'views/routing_new.html',
        routes = get_metadata(),
        depots = get_keys('routing')['locations']['depots'],
        drivers = get_keys('routing')['drivers'],
        admin=g.user.admin,
        group=g.group)
