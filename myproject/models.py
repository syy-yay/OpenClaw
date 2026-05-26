from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# 任务-标签 关联表（多对多）
task_tags = db.Table('task_tags',
    db.Column('task_id', db.Integer, db.ForeignKey('tasks.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id'), primary_key=True),
)


class Task(db.Model):
    __tablename__ = 'tasks'

    PRIORITY_MAP = {'high': 2, 'medium': 1, 'low': 0}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    assignee = db.Column(db.String(50), default='')
    status = db.Column(db.String(20), default='pending')
    priority = db.Column(db.String(10), default='medium')  # high, medium, low
    due_date = db.Column(db.Date, nullable=True)  # 截止日期
    start_date = db.Column(db.Date, nullable=True)  # 甘特图：计划开始日期
    duration_days = db.Column(db.Integer, default=1)  # 甘特图：预计持续天数
    progress_pct = db.Column(db.Integer, default=0)  # 甘特图：进度百分比 0-100
    depends_on_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)  # 前置任务

    # 前置任务关系
    depends_on = db.relationship('Task', remote_side='Task.id', backref=db.backref('dependent_tasks', lazy='dynamic'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def priority_order(self):
        return self.PRIORITY_MAP.get(self.priority, 99)

    tags = db.relationship('Tag', secondary=task_tags, lazy='subquery',
                            back_populates='tasks')

    def __repr__(self):
        return f'<Task {self.id}: {self.title} [{self.priority}]>'

    @property
    def days_remaining(self):
        """返回距截止日期剩余天数（负数表示已过期）"""
        if not self.due_date:
            return None
        delta = self.due_date - datetime.utcnow().date()
        return delta.days

    def to_dict(self):
        # 查找 assignee 对应用户（用于头像）
        assignee_user = None
        if self.assignee:
            assignee_user = User.query.filter_by(username=self.assignee).first()
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'assignee': self.assignee,
            'assignee_avatar': assignee_user.avatar_url if assignee_user else None,
            'assignee_initial': self.assignee[0].upper() if self.assignee else None,
            'status': self.status,
            'priority': self.priority,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'duration_days': self.duration_days,
            'progress_pct': self.progress_pct,
            'depends_on_id': self.depends_on_id,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'days_remaining': self.days_remaining,
            'tags': [{'id': t.id, 'name': t.name, 'color': t.color} for t in self.tags],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }



class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True, default=None)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    role = db.Column(db.String(20), default='user')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @classmethod
    def find_by_identity(cls, identity):
        if not identity:
            return None
        import re
        if re.match(r'^1[3-9]\d{9}$', identity.strip()):
            return cls.query.filter_by(phone=identity.strip()).first()
        if '@' in identity:
            return cls.query.filter_by(email=identity.lower().strip()).first()
        return cls.query.filter_by(username=identity.strip()).first()

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
            d['avatar_url'] = self.avatar_url
            d['created_at'] = self.created_at.isoformat() if self.created_at else None
            d['updated_at'] = self.updated_at.isoformat() if self.updated_at else None
        return d

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Tag(db.Model):
    # 任务标签
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    color = db.Column(db.String(7), default='#4a6fa5')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', secondary='task_tags', lazy='subquery',
                            back_populates='tags')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'color': self.color,
            'task_count': len(self.tasks),
        }

    def __repr__(self):
        return '<Tag {}: {}>'.format(self.id, self.name)



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


class Note(db.Model):
    """任务备注"""
    __tablename__ = 'notes'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    task = db.relationship('Task', backref=db.backref('notes', lazy='dynamic', order_by='Note.created_at'))
    user = db.relationship('User', backref=db.backref('notes', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'user': {
                'id': self.user.id,
                'username': self.user.username,
                'avatar_url': self.user.avatar_url,
            },
            'content': self.content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<Note {self.id} on Task {self.task_id}>'


class Attachment(db.Model):
    """任务附件"""
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    original_name = db.Column(db.String(200), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task = db.relationship('Task', backref=db.backref('attachments', lazy='dynamic', order_by='Attachment.created_at.desc()'))
    uploader = db.relationship('User', backref=db.backref('attachments', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'task_id': self.task_id,
            'filename': self.filename,
            'original_name': self.original_name,
            'file_size': self.file_size,
            'mime_type': self.mime_type,
            'uploader': {'id': self.uploader.id, 'username': self.uploader.username} if self.uploader else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'download_url': '/api/attachments/' + str(self.id) + '/download',
        }

    def __repr__(self):
        return '<Attachment {}: {}>'.format(self.id, self.original_name)
