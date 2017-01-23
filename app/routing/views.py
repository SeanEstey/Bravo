'''app.routing.views'''
from flask import g, render_template
from flask_login import login_required
from .. import get_keys
from . import routing
from .main import get_metadata
from .tasks import analyze_routes

#-------------------------------------------------------------------------------
@routing.route('', methods=['GET'])
@login_required
def show_routing():
    analyze_routes.delay(days=5)

    return render_template(
      'views/routing.html',
      routes = get_metadata(),
      depots = get_keys('routing')['locations']['depots'],
      drivers = get_keys('routing')['drivers'],
      admin=g.user.admin,
      agency=g.user.agency)
