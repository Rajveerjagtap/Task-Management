from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from pydantic import ValidationError
from models import User, UserRegister, UserLogin, db
from utils import create_access_token

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = UserRegister(**request.json)
    except ValidationError as e:
        return jsonify(error=e.errors()), 400

    if User.query.filter_by(email=data.email).first():
        return jsonify(message="Email already registered"), 409

    hashed_pw = generate_password_hash(data.password)
    new_user = User(username=data.username, email=data.email, password=hashed_pw)
    db.session.add(new_user)
    db.session.commit()
    return jsonify(message="User registered successfully"), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = UserLogin(**request.json)
    except ValidationError as e:
        return jsonify(error=e.errors()), 400

    user = User.query.filter_by(email=data.email).first()
    if user and check_password_hash(user.password, data.password):
        access_token = create_access_token(identity=user.email)
        return jsonify(access_token=access_token), 200

    return jsonify(message="Invalid credentials"), 401