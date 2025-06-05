from flask import request, jsonify, current_app
import datetime
import jwt
from functools import wraps


def create_access_token(identity, expires_delta=None):
    expire = datetime.datetime.utcnow() + (expires_delta if expires_delta else current_app.config['JWT_ACCESS_TOKEN_EXPIRES'])
    payload = {
        "sub": identity,
        "iat": datetime.datetime.utcnow(),
        "exp": expire
    }
    token = jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def jwt_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"msg": "Missing or invalid Authorization header"}), 401

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            request.user_identity = payload.get("sub")
        except jwt.ExpiredSignatureError:
            return jsonify({"msg": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"msg": "Invalid token"}), 401
        
        return fn(*args, **kwargs)
    return wrapper

def get_jwt_identity():
    return getattr(request, "user_identity", None)

