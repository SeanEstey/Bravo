'''app.auth.views'''
from flask import g, request, render_template, redirect, url_for, jsonify, session
from flask_login import login_required
from . import auth

#-------------------------------------------------------------------------------
@auth.route('/login', methods=['GET'])
def show_login():

    msg = request.args.get('msg')
    return render_template(
        'views/login.html',
        msg=msg if msg else 'Welcome!')
