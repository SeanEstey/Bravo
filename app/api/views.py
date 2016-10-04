# api views

from app import gsheets

from flask import Blueprint, request, render_template, \
                g, session, redirect, url_for

from app import db

import app.api.routing_api

api = Blueprint('api', __name__, url_prefix='/api')


gsheets.test_test()

@api.route('/api_url', methods=['GET','POST'])
def some_func():
    app.api.routing_api.do_api()
    return 'OK'
