from flask_sqlalchemy import SQLAlchemy
from pydantic import BaseModel, EmailStr, constr
from enum import Enum
from typing import Optional

db = SQLAlchemy()

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
