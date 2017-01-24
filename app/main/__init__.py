from flask import Blueprint, current_app

main = Blueprint('main', __name__, template_folder='templates')

from . import views
