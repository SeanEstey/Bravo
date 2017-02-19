'''app.booker.__init__'''
from flask import Blueprint

booker = Blueprint(
    'booker',
    __name__,
    url_prefix='/booker',
    static_folder='./static',
    template_folder='./templates')

from . import views


