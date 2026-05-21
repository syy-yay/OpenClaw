from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re

db = SQLAlchemy()


class Task(db.Model):
    __tablename__ = 'tasks'

    PRIORITY_MAP = {'high': 2, 'medium': 1, 'low': 0}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    assignee = db.Column(db.String(50), default='')
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(10), default='medium')  # high, medium, low
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def priority_order(self):
        return self.PRIORITY_MAP.get(self.priority, 99)

    def __repr__(self):
        return f'<Task {self.id}: {self.title} [{self.priority}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assignee': self.assignee,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }



class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True, default=None)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    oauth_provider = db.Column(db.String(20), nullable=True)
    oauth_id = db.Column(db.String(100), nullable=True)

    # ---------- 密码 ----------
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # ---------- 身份查找 ----------
    @classmethod
    def find_by_identity(cls, identity):
        if not identity:
            return None
        if re.match(r'^1[3-9]\d{9}$', identity.strip()):
            return cls.query.filter_by(phone=identity.strip()).first()
        if '@' in identity:
            return cls.query.filter_by(email=identity.lower().strip()).first()
        return cls.query.filter_by(username=identity.strip()).first()

    # ---------- 权限 ----------
    @property
    def is_admin(self):
        return self.role == 'admin'

    def to_dict(self, full=False):
        d = {
            'id': self.id,
            'username': self.username,
            'role': self.role,
        }
        if full:
            d['email'] = self.email
            d['phone'] = self.phone
            d['avatar_url'] = self.avatar_url
            d['created_at'] = self.created_at.isoformat() if self.created_at else None
            d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
            d['last_login'] = self.last_login.isoformat() if self.last_login else None
            d['oauth_provider'] = self.oauth_provider
        return d

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class OAuthToken(db.Model):
    """第三方登录令牌"""
    __tablename__ = 'oauth_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider = db.Column(db.String(20), nullable=False)
    access_token = db.Column(db.String(500), nullable=False)
    refresh_token = db.Column(db.String(500), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('oauth_tokens', lazy=True))

    def is_expired(self):
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at


class LoginLog(db.Model):
    """登录日志"""
    __tablename__ = 'login_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username_attempted = db.Column(db.String(80), nullable=True)
    ip_address = db.Column(db.String(45), nullable=False)
    user_agent = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, nullable=False)
    failure_reason = db.Column(db.String(100), nullable=True)
    login_method = db.Column(db.String(20), default='password')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('login_logs', lazy=True))
class Comment(db.Model):
    """任务评论"""
    __tablename__ = 'comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_deleted = db.Column(db.Boolean, default=False)  # 软删除

    task = db.relationship('Task', backref=db.backref('comments', lazy='dynamic', order_by='Comment.created_at'))
    user = db.relationship('User', backref=db.backref('comments', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': self.user.avatar_url,
            },
            'content': self.content if not self.is_deleted else '[评论已被删除]',
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_deleted': self.is_deleted,
        }

    def __repr__(self):
        return f'<Comment {self.id} on Task {self.task_id}>'
