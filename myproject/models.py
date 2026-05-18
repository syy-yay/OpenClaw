from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import re

db = SQLAlchemy()


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    assignee = db.Column(db.String(50), default='')
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)  # Nullable for OAuth users
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    role = db.Column(db.String(20), default='user')  # admin, user, guest
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    oauth_provider = db.Column(db.String(20), nullable=True)  # github, wechat, qq
    oauth_id = db.Column(db.String(100), nullable=True)  # Provider's user ID

    # ---------- 密码 ----------
    def set_password(self, password):
        """设置密码哈希"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """检查密码是否正确"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # ---------- 身份查找 ----------
    @classmethod
    def find_by_identity(cls, identity):
        """
        通过用户名 / 邮箱 / 手机号查找用户。
        identity: str — 输入内容，自动匹配最合适的字段。
        """
        if not identity:
            return None

        # 手机号判断（中国大陆格式）
        if re.match(r'^1[3-9]\d{9}$', identity.strip()):
            return cls.query.filter_by(phone=identity.strip()).first()

        # 邮箱判断
        if '@' in identity:
            return cls.query.filter_by(email=identity.lower().strip()).first()

        # 默认当作用户名
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
            d['created_at'] = self.created_at.isoformat() if self.created_at else None
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
    provider = db.Column(db.String(20), nullable=False)  # github, wechat, qq
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
    username_attempted = db.Column(db.String(80), nullable=True)  # 登录尝试的用户名
    ip_address = db.Column(db.String(45), nullable=False)  # IPv6 support
    user_agent = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, nullable=False)
    failure_reason = db.Column(db.String(100), nullable=True)  # 失败原因
    login_method = db.Column(db.String(20), default='password')  # password, github, wechat, qq
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('login_logs', lazy=True))
