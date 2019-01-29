from . import main
from ..models import APIError
from flask import jsonify
@main.errorhandler(APIError)
def err(e):
	return jsonify(e.todict())