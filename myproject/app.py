#!/usr/bin/env python3
"""团队任务管理系统 - 后端主程序（开放访问版）"""
import os, re, time
from datetime import datetime, timedelta, date
from functools import wraps

import jwt
from flask import Flask, request, jsonify, render_template
from models import db, Task, User, Tag, task_tags, Comment, Note


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # JWT 配置
    JWT_SECRET = os.environ.get('JWT_SECRET', 'jwt-secret-change-in-production')
    JWT_ALGORITHM = 'HS256'
    JWT_EXPIRATION_HOURS = 24

    db.init_app(app)

    # ==================== 数据库初始化 ====================
    with app.app_context():
        db.create_all()

        # 创建默认管理员（首次运行）
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', email='admin@example.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()

    # ==================== 页面路由 ====================
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login_page():
        return render_template('login.html')

    @app.route('/register')
    def register_page():
        return render_template('register.html')

    # ==================== JWT 辅助函数 ====================
    def generate_token(user_id):
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            'iat': datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_token(token):
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload['user_id']
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def login_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return jsonify({'error': '未提供认证令牌'}), 401
            token = auth[7:]
            user_id = verify_token(token)
            if not user_id:
                return jsonify({'error': '令牌无效或已过期'}), 401
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({'error': '用户不存在或已禁用'}), 401
            request.current_user = user
            return f(*args, **kwargs)
        return decorated

    # ==================== 认证 API ====================
    @app.route('/api/auth/register', methods=['POST'])
    def register():
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = data.get('password', '')
        email = (data.get('email') or '').strip().lower()

        if not username or not password or not email:
            return jsonify({'success': False, 'message': '用户名、密码和邮箱不能为空'}), 400

        if len(username) < 3 or len(username) > 20:
            return jsonify({'success': False, 'message': '用户名长度必须在3-20个字符之间'}), 400

        if len(password) < 6:
            return jsonify({'success': False, 'message': '密码长度至少6位'}), 400

        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': '用户名已存在'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': '邮箱已被使用'}), 400

        try:
            user = User(username=username, email=email, role='user')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            token = generate_token(user.id)
            return jsonify({
                'success': True, 'message': '注册成功',
                'token': token,
                'user': user.to_dict()
            }), 201
        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'message': '注册失败，请稍后重试'}), 500

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json() or {}
        identity = (data.get('identity') or '').strip()
        password = data.get('password', '')

        if not identity or not password:
            return jsonify({'success': False, 'message': '请输入账号和密码'}), 400

        user = User.find_by_identity(identity)
        if not user or not user.check_password(password) or not user.is_active:
            return jsonify({'success': False, 'message': '账号或密码错误'}), 401

        token = generate_token(user.id)
        return jsonify({
            'success': True, 'message': '登录成功',
            'token': token,
            'user': user.to_dict()
        })

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        return jsonify({'success': True, 'message': '已退出登录'})

    @app.route('/api/auth/me', methods=['GET'])
    @login_required
    def auth_me():
        return jsonify({'authenticated': True, 'user': request.current_user.to_dict(full=True)})

    # ==================== 任务 API ====================
    @app.route('/api/tasks', methods=['GET'])
    def get_tasks():
        sort_by = request.args.get('sort', 'priority')
        order = request.args.get('order', 'desc')
        tag_filter = request.args.get('tag')

        tasks = Task.query.all()

        if tag_filter:
            tasks = [t for t in tasks if tag_filter in [tag.name for tag in t.tags]]

        if sort_by == 'priority':
            tasks.sort(key=lambda t: t.priority_order)
            if order == 'desc':
                tasks.reverse()

        return jsonify([t.to_dict() for t in tasks])

    @app.route('/api/tasks/<int:task_id>', methods=['GET'])
    def get_task_detail(task_id):
        task = Task.query.get_or_404(task_id)
        result = task.to_dict()
        result['notes'] = [n.to_dict() for n in task.notes.order_by(Note.created_at.asc()).all()]
        return jsonify(result)

    @app.route('/api/tasks', methods=['POST'])
    def create_task():
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({'error': '标题不能为空'}), 400

        priority = data.get('priority', 'medium')
        if priority not in ('high', 'medium', 'low'):
            return jsonify({'error': '优先级无效（high/medium/low）'}), 400

        due_date = None
        if 'due_date' in data and data['due_date']:
            try:
                due_date = date.fromisoformat(data['due_date'])
            except (ValueError, TypeError):
                return jsonify({'error': '日期格式无效，请使用 YYYY-MM-DD'}), 400

        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            assignee=data.get('assignee', ''),
            status=data.get('status', 'pending'),
            priority=priority,
            due_date=due_date,
        )
        db.session.add(task)
        db.session.commit()

        if 'tags' in data and isinstance(data['tags'], list):
            for tag_name in data['tags']:
                tag = Tag.query.filter_by(name=tag_name).first()
                if tag:
                    task.tags.append(tag)
            db.session.commit()

        return jsonify(task.to_dict()), 201

    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    def update_task(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json()

        task.title = data.get('title', task.title)
        task.description = data.get('description', task.description)
        task.assignee = data.get('assignee', task.assignee)
        task.status = data.get('status', task.status)

        if 'priority' in data:
            if data['priority'] not in ('high', 'medium', 'low'):
                return jsonify({'error': '优先级无效（high/medium/low）'}), 400
            task.priority = data['priority']

        if 'due_date' in data:
            if data['due_date']:
                try:
                    task.due_date = date.fromisoformat(data['due_date'])
                except (ValueError, TypeError):
                    return jsonify({'error': '日期格式无效，请使用 YYYY-MM-DD'}), 400
            else:
                task.due_date = None

        db.session.commit()
        return jsonify(task.to_dict())

    @app.route('/api/tasks/<int:task_id>/progress', methods=['GET'])
    def get_task_progress(task_id):
        task = Task.query.get_or_404(task_id)
        total_tasks = Task.query.count()
        completed_tasks = Task.query.filter_by(status='completed').count()

        return jsonify({
            'task_id': task.id,
            'status': task.status,
            'task': task.to_dict(),
            'progress': {
                'total': total_tasks,
                'completed': completed_tasks,
                'percentage': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
        })

    # ==================== 评论 API ====================
    @app.route('/api/tasks/<int:task_id>/comments', methods=['GET'])
    def get_task_comments(task_id):
        task = Task.query.get_or_404(task_id)
        comments = Comment.query.filter_by(task_id=task.id, is_deleted=False).order_by(Comment.created_at.asc()).all()
        return jsonify([c.to_dict() for c in comments])

    @app.route('/api/tasks/<int:task_id>/comments', methods=['POST'])
    def create_comment(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json() or {}

        content_text = (data.get('content') or '').strip()
        if not content_text:
            return jsonify({'error': '评论内容不能为空'}), 400
        if len(content_text) > 5000:
            return jsonify({'error': '评论内容不能超过5000字符'}), 400

        # Use first system user or create one for anonymous comments
        user = User.query.first()
        if not user:
            user = User(username='system', email='system@local')
            db.session.add(user)
            db.session.commit()

        comment = Comment(task_id=task.id, user_id=user.id, content=content_text)
        db.session.add(comment)
        db.session.commit()

        return jsonify({'success': True, 'comment': comment.to_dict()}), 201

    @app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
    def delete_comment(comment_id):
        comment = Comment.query.get_or_404(comment_id)
        comment.is_deleted = True
        comment.content = ''
        db.session.commit()
        return jsonify({'success': True, 'message': '评论已删除'})

    # ==================== 标签 API ====================
    @app.route('/api/tags', methods=['GET'])
    def get_tags():
        tags = Tag.query.all()
        return jsonify([t.to_dict() for t in tags])

    @app.route('/api/tags', methods=['POST'])
    def create_tag():
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()
        if not name:
            return jsonify({'error': '标签名称不能为空'}), 400
        if len(name) > 50:
            return jsonify({'error': '标签名称不能超过50个字符'}), 400

        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return jsonify({'error': '标签名称已存在', 'tag': existing.to_dict()}), 400

        color = data.get('color', '#4a6fa5')
        tag = Tag(name=name, color=color)
        db.session.add(tag)
        db.session.commit()

        return jsonify({'success': True, 'tag': tag.to_dict()}), 201

    @app.route('/api/tags/<int:tag_id>', methods=['DELETE'])
    def delete_tag(tag_id):
        tag = Tag.query.get_or_404(tag_id)
        tag.tasks = []
        db.session.delete(tag)
        db.session.commit()
        return jsonify({'success': True, 'message': '标签已删除'})

    @app.route('/api/tasks/<int:task_id>/tags', methods=['POST'])
    def add_task_tag(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json() or {}
        tag_name = (data.get('tag') or '').strip()

        if not tag_name:
            return jsonify({'error': '标签名称不能为空'}), 400

        tag = Tag.query.filter_by(name=tag_name).first()
        if not tag:
            return jsonify({'error': f'标签 "{tag_name}" 不存在'}), 404

        if tag in task.tags:
            return jsonify({'error': '该任务已包含此标签'}), 400

        task.tags.append(tag)
        db.session.commit()
        return jsonify({'success': True, 'task': task.to_dict()})

    @app.route('/api/tasks/<int:task_id>/tags/<int:tag_id>', methods=['DELETE'])
    def remove_task_tag(task_id, tag_id):
        task = Task.query.get_or_404(task_id)
        tag = Tag.query.get_or_404(tag_id)

        if tag not in task.tags:
            return jsonify({'error': '该任务不包含此标签'}), 404

        task.tags.remove(tag)
        db.session.commit()
        return jsonify({'success': True, 'task': task.to_dict()})

    # ==================== 备注 API ====================
    @app.route('/api/tasks/<int:task_id>/notes', methods=['POST'])
    def create_note(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json() or {}

        content_text = (data.get('content') or '').strip()
        if not content_text:
            return jsonify({'error': '备注内容不能为空'}), 400
        if len(content_text) > 10000:
            return jsonify({'error': '备注内容不能超过10000字符'}), 400

        user = User.query.first()
        if not user:
            user = User(username='system', email='system@local')
            db.session.add(user)
            db.session.commit()

        note = Note(task_id=task.id, user_id=user.id, content=content_text)
        db.session.add(note)
        db.session.commit()
        return jsonify({'success': True, 'note': note.to_dict()}), 201

    @app.route('/api/notes/<int:note_id>', methods=['PUT'])
    def update_note(note_id):
        note = Note.query.get_or_404(note_id)
        data = request.get_json() or {}
        content_text = (data.get('content') or '').strip()
        if not content_text:
            return jsonify({'error': '备注内容不能为空'}), 400
        if len(content_text) > 10000:
            return jsonify({'error': '备注内容不能超过10000字符'}), 400

        note.content = content_text
        db.session.commit()
        return jsonify({'success': True, 'note': note.to_dict()})

    @app.route('/api/notes/<int:note_id>', methods=['DELETE'])
    def delete_note(note_id):
        note = Note.query.get_or_404(note_id)
        db.session.delete(note)
        db.session.commit()
        return jsonify({'success': True, 'message': '备注已删除'})

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
