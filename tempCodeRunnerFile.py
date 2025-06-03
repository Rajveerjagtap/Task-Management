from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from pydantic import BaseModel, EmailStr, ValidationError, constr
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum
import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://flaskuser:flaskpass@localhost:5432/flaskdb'
app.config['JWT_SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)

db = SQLAlchemy(app)
jwt = JWTManager(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)  # updated length

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.String(10), nullable=False)
    status = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


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

@app.route('/register', methods=['POST'])
def register():
    try:
        data = UserRegister(**request.json)
    except ValidationError as e:
        return jsonify(error=e.errors()), 400

    if User.query.filter_by(email=data.email).first():
        return jsonify(message="Already Registered"), 409

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
@jwt_required()
def create_task():
    try:
        data = TaskSchema(**request.json)
        due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format, use YYYY-MM-DD"), 400

    user_email = get_jwt_identity()
    user = User.query.filter_by(email=user_email).first()

    task = Task(
        title=data.title,
        description=data.description,
        due_date=due_date,
        priority=data.priority,
        status=data.status,
        user_id=user.id
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(message="Task created"), 201

@app.route('/tasks', methods=['GET'])
@jwt_required()
def get_tasks():
    user_email = get_jwt_identity()
    user = User.query.filter_by(email=user_email).first()
    query = Task.query.filter_by(user_id=user.id)

    # Filters
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
        return jsonify(message="Invalid date format, use YYYY-MM-DD"), 400

    if priority in ['High', 'Medium', 'Low']:
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

    sort_column = getattr(Task, sort_by)
    query = query.order_by(sort_column.desc() if order == 'desc' else sort_column.asc())

    tasks = query.all()
    return jsonify([
        {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "due_date": task.due_date.isoformat(),
            "priority": task.priority,
            "status": task.status
        } for task in tasks
    ])

@app.route('/tasks/<int:task_id>', methods=['GET'])
@jwt_required()
def get_task(task_id):
    user_email = get_jwt_identity()
    user = User.query.filter_by(email=user_email).first()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404
    return jsonify({
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date.isoformat(),
        "priority": task.priority,
        "status": task.status
    })

@app.route('/tasks/<int:task_id>', methods=['PUT'])
@jwt_required()
def update_task(task_id):
    user_email = get_jwt_identity()
    user = User.query.filter_by(email=user_email).first()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404

    try:
        data = TaskSchema(**request.json)
        task.title = data.title
        task.description = data.description
        task.due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
        task.priority = data.priority
        task.status = data.status
        db.session.commit()
        return jsonify(message="Task updated"), 200
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format"), 400

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    user_email = get_jwt_identity()
    user = User.query.filter_by(email=user_email).first()
    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404
    db.session.delete(task)
    db.session.commit()
    return jsonify(message="Task deleted"), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
