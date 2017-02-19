'''app.notify.__init__'''
from flask import Blueprint

notify = Blueprint(
    'notify',
    __name__,
    url_prefix='/notify',
    static_folder='./static',
    template_folder='./templates')

from . import views
