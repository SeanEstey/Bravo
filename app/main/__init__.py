from flask import Blueprint, current_app

main = Blueprint('main', __name__)

from . import views
