'''app.routing.__init__'''
from flask import Blueprint

routing = Blueprint(
    'routing',
    __name__,
    url_prefix='/routing',
    static_folder='./static',
    template_folder='./templates')

from . import views


