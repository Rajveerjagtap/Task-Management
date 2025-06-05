from flask import Blueprint, request, jsonify
from models import User, db
from utils import jwt_required, get_jwt_identity

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/feature', methods=['GET'])
def feature():
    """Placeholder feature endpoint"""
    return jsonify(message="Feature endpoint - to be implemented"), 200

@profile_bp.route('/profile', methods=['GET'])
@jwt_required
def get_profile():
    """Get user profile information"""
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email
    }), 200