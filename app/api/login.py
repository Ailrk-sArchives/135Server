from flask import jsonify
from . import api
from ..models import User


@api.route('/login')
def login():
    return "login"

