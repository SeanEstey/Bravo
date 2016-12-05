from flask import Blueprint, current_app

booker = Blueprint('booker', __name__, url_prefix='/booker')

from . import views


