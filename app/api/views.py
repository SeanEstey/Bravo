# api views

from app import gsheets

from flask import Blueprint, request, render_template, \
                g, session, redirect, url_for

from app import db


api = Blueprint('api', __name__, url_prefix='/api')


@api.route('/api_url', methods=['GET','POST'])
def some_func():
    app.api.routing_api.do_api()
    return 'OK'
