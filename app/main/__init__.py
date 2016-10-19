from flask import Blueprint, current_app

main = Blueprint('main', __name__)

from . import views

# Comment when not running integration tests
from . import integration_test_views
