from flask import Blueprint, request, jsonify
from pydantic import ValidationError
from models import User, Task, TaskSchema, TaskUpdateSchema, PriorityEnum, db
from utils import jwt_required, get_jwt_identity
import datetime
from collections import OrderedDict

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/tasks', methods=['POST'])
@jwt_required
def create_task():
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

@tasks_bp.route('/tasks', methods=['GET'])
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

@tasks_bp.route('/tasks/<int:task_id>', methods=['GET'])
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

@tasks_bp.route('/tasks/<int:task_id>', methods=['PUT'])
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

@tasks_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
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