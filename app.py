from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from pydantic import BaseModel, EmailStr, ValidationError, constr
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum
import datetime
import jwt
from functools import wraps
from typing import Optional
from collections import OrderedDict

SWAGGER_URL = '/api/docs'  
API_URL = '/static/swagger.json'  

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://flaskuser:flaskpass@localhost:5432/flaskdb'
app.config['JWT_SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,  
    API_URL,
    config={  
        'app_name': "Test application"
    },
   
)

app.register_blueprint(swaggerui_blueprint)

db = SQLAlchemy(app)

def create_access_token(identity, expires_delta=None):
    expire = datetime.datetime.utcnow() + (expires_delta if expires_delta else app.config['JWT_ACCESS_TOKEN_EXPIRES'])
    payload = {
        "sub": identity,
        "iat": datetime.datetime.utcnow(),
        "exp": expire
    }
    token = jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
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
            payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            request.user_identity = payload.get("sub")
        except jwt.ExpiredSignatureError:
            return jsonify({"msg": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"msg": "Invalid token"}), 401
        
        return fn(*args, **kwargs)
    return wrapper

def get_jwt_identity():
    return getattr(request, "user_identity", None)


class User(db.Model):
    __tablename__ = 'users' 
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(10), nullable=False)
    status = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: constr(min_length=6)

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PriorityEnum(str, Enum):
    High = "High"
    Medium = "Medium"
    Low = "Low"

class TaskSchema(BaseModel):
    title: constr(max_length=100)
    description: str = None
    due_date: str
    priority: PriorityEnum
    status: bool

class TaskUpdateSchema(BaseModel):
    title: Optional[constr(max_length=100)] = None
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[PriorityEnum] = None
    status: Optional[bool] = None
    

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/register', methods=['POST'])
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

@app.route('/login', methods=['POST'])
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

@app.route('/tasks', methods=['POST'])
@jwt_required
def create_task():
    try:
        data = TaskSchema(**request.json)
        due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format. Use YYYY-MM-DD."), 400
#pass payload in function it self 
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

    task = Task(
        title=data.title,
        description=data.description,
        due_date=due_date,
        priority=data.priority.value,
        status=data.status,
        user_id=user.id
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(message="Task created successfully"), 201

@app.route('/tasks', methods=['GET'])
@jwt_required
def get_tasks():
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404
    query = Task.query.filter_by(user_id=user.id)

    due_before = request.args.get('due_before')
    due_after = request.args.get('due_after')
    priority = request.args.get('priority')
    status = request.args.get('status')
    sort_by = request.args.get('sort_by', 'due_date')
    order = request.args.get('order', 'asc')

    try:
        if due_before:
            query = query.filter(Task.due_date <= datetime.datetime.strptime(due_before, '%Y-%m-%d').date())
        if due_after:
            query = query.filter(Task.due_date >= datetime.datetime.strptime(due_after, '%Y-%m-%d').date())
    except ValueError:
        return jsonify(message="Invalid date format. Use YYYY-MM-DD."), 400

    if priority in PriorityEnum.__members__:
        query = query.filter_by(priority=priority)

    if status is not None:
        if status.lower() in ['true', 'false']:
            query = query.filter_by(status=status.lower() == 'true')
        else:
            return jsonify(message="Status must be 'true' or 'false'"), 400

    if sort_by not in ['due_date', 'priority']:
        return jsonify(message="Invalid sort_by value"), 400

    if order not in ['asc', 'desc']:
        return jsonify(message="Invalid order value"), 400

    if sort_by == 'priority':
        priority_order = db.case(
            (Task.priority == 'High', 1),
            (Task.priority == 'Medium', 2),
            (Task.priority == 'Low', 3),
            else_=4
        )
        if order == 'desc':
            query = query.order_by(priority_order.desc())
        else:
            query = query.order_by(priority_order.asc())
    else:
        sort_column = getattr(Task, sort_by)
        priority_order = db.case(
            (Task.priority == 'High', 1),
            (Task.priority == 'Medium', 2),
            (Task.priority == 'Low', 3),
            else_=4
        )
        if order == 'desc':
            query = query.order_by(sort_column.desc(), priority_order.asc())
        else:
            query = query.order_by(sort_column.asc(), priority_order.asc())

    tasks = query.all()
    return jsonify([
        OrderedDict([
            ("id", task.id),
            ("title", task.title),
            ("description", task.description),
            ("due_date", task.due_date.isoformat()),
            ("priority", task.priority),
            ("status", task.status)
        ]) for task in tasks
    ])
#pydentic class return 

@app.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required
def get_task(task_id):
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404
    return jsonify(OrderedDict([
        ("id", task.id),
        ("title", task.title),
        ("description", task.description),
        ("due_date", task.due_date.isoformat()),
        ("priority", task.priority),
        ("status", task.status)
    ]))
@app.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required
def update_task(task_id):
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404

    try:
        data = TaskUpdateSchema(**request.json)
        
        if data.title is not None:
            task.title = data.title
        if data.description is not None:
            task.description = data.description
        if data.due_date is not None:
            task.due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
        if data.priority is not None:
            task.priority = data.priority.value
        if data.status is not None:
            task.status = data.status
            
        db.session.commit()
        return jsonify(OrderedDict([
            ("id", task.id),
            ("title", task.title),
            ("description", task.description),
            ("due_date", task.due_date.isoformat()),
            ("priority", task.priority),
            ("status", task.status)
        ])), 200
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format. Use YYYY-MM-DD."), 400

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required
def delete_task(task_id):
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404

    db.session.delete(task)
    db.session.commit()
    return jsonify(message="Task deleted successfully"), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)