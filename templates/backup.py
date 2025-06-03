from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from pydantic import BaseModel, EmailStr, ValidationError, constr
from werkzeug.security import generate_password_hash, check_password_hash
from enum import Enum
import datetime
import jwt
from functools import wraps
from flasgger import Swagger

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql+psycopg2://flaskuser:flaskpass@localhost:5432/flaskdb'
app.config['JWT_SECRET_KEY'] = 'supersecretkey'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = datetime.timedelta(days=1)

db = SQLAlchemy(app)
swagger = Swagger(app)

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

@app.route('/')
def landing():
    """
    Landing page
    ---
    tags:
      - General
    responses:
      200:
        description: Landing page rendered
    """
    return render_template('landing.html')

@app.route('/register', methods=['POST'])
def register():
    """
    Register a new user
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - username
            - email
            - password
          properties:
            username:
              type: string
              description: Username for the new user
            email:
              type: string
              format: email
              description: Email address
            password:
              type: string
              minLength: 6
              description: Password (minimum 6 characters)
    responses:
      201:
        description: User registered successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "User registered successfully"
      400:
        description: Validation error
        schema:
          type: object
          properties:
            error:
              type: array
              items:
                type: object
      409:
        description: Email already registered
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Email already registered"
    """
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
    """
    Login user
    ---
    tags:
      - Authentication
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
              format: email
              description: User email
            password:
              type: string
              description: User password
    responses:
      200:
        description: Login successful
        schema:
          type: object
          properties:
            access_token:
              type: string
              description: JWT access token
      400:
        description: Validation error
      401:
        description: Invalid credentials
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Invalid credentials"
    """
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
    """
    Create a new task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - title
            - due_date
            - priority
            - status
          properties:
            title:
              type: string
              maxLength: 100
              description: Task title
            description:
              type: string
              description: Task description
            due_date:
              type: string
              format: date
              description: Due date (YYYY-MM-DD)
            priority:
              type: string
              enum: [High, Medium, Low]
              description: Task priority
            status:
              type: boolean
              description: Task status (true for completed, false for pending)
    responses:
      201:
        description: Task created successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Task created successfully"
      400:
        description: Validation error
      404:
        description: User not found
      401:
        description: Unauthorized
    """
    try:
        data = TaskSchema(**request.json)
        due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format. Use YYYY-MM-DD."), 400

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
    """
    Get user tasks with optional filtering
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: query
        name: due_before
        type: string
        format: date
        description: Filter tasks due before this date (YYYY-MM-DD)
      - in: query
        name: due_after
        type: string
        format: date
        description: Filter tasks due after this date (YYYY-MM-DD)
      - in: query
        name: priority
        type: string
        enum: [High, Medium, Low]
        description: Filter by priority
      - in: query
        name: status
        type: string
        enum: [true, false]
        description: Filter by status
      - in: query
        name: sort_by
        type: string
        enum: [due_date, priority]
        default: due_date
        description: Sort tasks by field
      - in: query
        name: order
        type: string
        enum: [asc, desc]
        default: asc
        description: Sort order
    responses:
      200:
        description: List of tasks
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              title:
                type: string
              description:
                type: string
              due_date:
                type: string
                format: date
              priority:
                type: string
              status:
                type: boolean
      404:
        description: User not found
      401:
        description: Unauthorized
    """
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
        status_bool = status.lower() == 'true'
        query = query.filter_by(status=status_bool)

    if sort_by not in ['due_date', 'priority']:
        sort_by = 'due_date'

    sort_column = getattr(Task, sort_by)
    if order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

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
@jwt_required
def get_task(task_id):
    """
    Get a specific task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: integer
        required: true
        description: ID of the task to retrieve
    responses:
      200:
        description: Task details
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            description:
              type: string
            due_date:
              type: string
              format: date
            priority:
              type: string
            status:
              type: boolean
      404:
        description: Task not found or user not found
      401:
        description: Unauthorized
    """
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

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
@jwt_required
def update_task(task_id):
    """
    Update a task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: integer
        required: true
        description: ID of the task to update
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
              maxLength: 100
            description:
              type: string
            due_date:
              type: string
              format: date
            priority:
              type: string
              enum: [High, Medium, Low]
            status:
              type: boolean
    responses:
      200:
        description: Task updated successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Task updated successfully"
      400:
        description: Validation error
      404:
        description: Task not found or user not found
      401:
        description: Unauthorized
    """
    user = User.query.filter_by(email=get_jwt_identity()).first()
    if not user:
        return jsonify(message="User not found"), 404

    task = Task.query.filter_by(id=task_id, user_id=user.id).first()
    if not task:
        return jsonify(message="Task not found"), 404

    try:
        data = TaskSchema(**request.json)
        task.title = data.title
        task.description = data.description
        task.due_date = datetime.datetime.strptime(data.due_date, '%Y-%m-%d').date()
        task.priority = data.priority.value
        task.status = data.status
        db.session.commit()
        return jsonify(message="Task updated successfully"), 200
    except ValidationError as e:
        return jsonify(error=e.errors()), 400
    except ValueError:
        return jsonify(message="Invalid date format. Use YYYY-MM-DD."), 400

@app.route('/tasks/<int:task_id>', methods=['DELETE'])
@jwt_required
def delete_task(task_id):
    """
    Delete a task
    ---
    tags:
      - Tasks
    security:
      - Bearer: []
    parameters:
      - in: path
        name: task_id
        type: integer
        required: true
        description: ID of the task to delete
    responses:
      200:
        description: Task deleted successfully
        schema:
          type: object
          properties:
            message:
              type: string
              example: "Task deleted successfully"
      404:
        description: Task not found or user not found
      401:
        description: Unauthorized
    """
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
