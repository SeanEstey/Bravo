'''app.alice.__init__'''
from flask import Blueprint

alice = Blueprint(
    'alice',
    __name__,
    url_prefix='/alice',
    static_folder='./static',
    template_folder='./templates')

from . import views
