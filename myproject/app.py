#!/usr/bin/env python3
"""团队任务管理系统 - 后端主程序（开放访问版）"""
import os, re, time
from datetime import datetime, timedelta, date
from functools import wraps

import jwt
from flask import Flask, request, jsonify, render_template
from models import db, Task, User, Tag, task_tags, Comment, Note, Attachment, Notification


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

    @app.route('/gantt')
    def gantt_page():
        return render_template('gantt.html')

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
    @app.route('/api/tasks/stats', methods=['GET'])
    def get_task_stats():
        total = Task.query.count()
        pending = Task.query.filter_by(status='pending').count()
        in_progress = Task.query.filter_by(status='in-progress').count()
        completed = Task.query.filter_by(status='completed').count()

        # 优先级分布
        high = Task.query.filter_by(priority='high').count()
        medium = Task.query.filter_by(priority='medium').count()
        low = Task.query.filter_by(priority='low').count()

        # 标签分布
        tags = Tag.query.all()
        tag_stats = [{'name': t.name, 'count': len(t.tasks), 'color': t.color} for t in tags]

        # 超期统计
        from datetime import datetime as dt
        overdue = Task.query.filter(
            Task.due_date.isnot(None),
            Task.due_date < dt.utcnow().date(),
            Task.status != 'completed'
        ).count()
        due_today = Task.query.filter(
            Task.due_date == dt.utcnow().date(),
            Task.status != 'completed'
        ).count()
        due_soon = Task.query.filter(
            Task.due_date.isnot(None),
            Task.due_date <= dt.utcnow().date() + timedelta(days=2),
            Task.due_date > dt.utcnow().date(),
            Task.status != 'completed'
        ).count()

        # 有/无截止日期的任务
        with_due = Task.query.filter(Task.due_date.isnot(None)).count()
        without_due = Task.query.filter(Task.due_date.is_(None)).count()

        return jsonify({
            'total': total,
            'by_status': {
                'pending': pending,
                'in-progress': in_progress,
                'completed': completed,
            },
            'by_priority': {
                'high': high,
                'medium': medium,
                'low': low,
            },
            'by_tag': tag_stats,
            'due_date': {
                'overdue': overdue,
                'today': due_today,
                'soon': due_soon,
                'with_due_date': with_due,
                'without_due_date': without_due,
            },
            'completion_rate': round(completed / total * 100, 1) if total > 0 else 0,
        })

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

        valid_date_formats = ['Y-m-d']

        def _parse_date(val, field_name='date'):
            if not val:
                return None
            try:
                return date.fromisoformat(val)
            except (ValueError, TypeError):
                raise ValueError(f'{field_name} 格式无效，请使用 YYYY-MM-DD')

        try:
            due_date = _parse_date(data.get('due_date'), 'due_date')
            start_date = _parse_date(data.get('start_date'), 'start_date')
        except ValueError as e:
            return jsonify({'error': str(e)}), 400

        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            assignee=data.get('assignee', ''),
            status=data.get('status', 'pending'),
            priority=priority,
            due_date=due_date,
            start_date=start_date,
            duration_days=data.get('duration_days', 1),
            progress_pct=data.get('progress_pct', 0),
            depends_on_id=data.get('depends_on_id'),
            remind_before_minutes=data.get('remind_before_minutes'),
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

        valid_date_formats = ['Y-m-d']

        def _parse_date(val, field_name='date'):
            if not val:
                return None
            try:
                return date.fromisoformat(val)
            except (ValueError, TypeError):
                raise ValueError(f'{field_name} 格式无效，请使用 YYYY-MM-DD')

        if 'due_date' in data:
            task.due_date = _parse_date(data.get('due_date'))
        if 'start_date' in data:
            task.start_date = _parse_date(data.get('start_date'))
        if 'duration_days' in data:
            task.duration_days = data['duration_days']
        if 'progress_pct' in data:
            task.progress_pct = data['progress_pct']
        if 'depends_on_id' in data:
            task.depends_on_id = data['depends_on_id']
        if 'remind_before_minutes' in data:
            task.remind_before_minutes = data['remind_before_minutes']

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


    # ==================== 附件配置 ====================
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'zip', 'rar', 'csv', 'md', 'json', 'xml'}
    MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

    @app.route('/api/tasks/<int:task_id>/attachments', methods=['GET'])
    def get_attachments(task_id):
        task = Task.query.get_or_404(task_id)
        return jsonify([a.to_dict() for a in task.attachments.all()])

    @app.route('/api/tasks/<int:task_id>/attachments', methods=['POST'])
    def upload_attachments(task_id):
        task = Task.query.get_or_404(task_id)

        if 'files' not in request.files:
            return jsonify({'error': '未选择文件'}), 400

        files = request.files.getlist('files')
        if not files or all(f.filename == '' for f in files):
            return jsonify({'error': '未选择文件'}), 400

        uploaded = []
        errors = []

        for file in files:
            if file.filename == '':
                continue

            # 校验文件扩展名
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({'file': file.filename, 'error': f'不支持的文件类型 (.{ext})'})
                continue

            # 校验文件大小
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
            if size > MAX_FILE_SIZE:
                errors.append({'file': file.filename, 'error': '文件大小不能超过 20MB'})
                continue

            # 生成唯一文件名
            import uuid
            unique_name = f'{uuid.uuid4().hex}.{ext}'
            year_month = datetime.utcnow().strftime('%Y/%m')
            relative_dir = f'uploads/{year_month}'
            abs_dir = os.path.join(UPLOAD_FOLDER, relative_dir)
            os.makedirs(abs_dir, exist_ok=True)

            filepath = os.path.join(abs_dir, unique_name)
            file.save(filepath)

            # 获取上传者
            user = User.query.first()

            att = Attachment(
                task_id=task.id,
                filename=f'{relative_dir}/{unique_name}',
                original_name=file.filename,
                file_size=size,
                mime_type=file.content_type or 'application/octet-stream',
                uploader_id=user.id if user else None,
            )
            db.session.add(att)
            uploaded.append(att)

        db.session.commit()

        return jsonify({
            'success': True,
            'uploaded': [a.to_dict() for a in uploaded],
            'errors': errors,
        }), 201

    @app.route('/api/attachments/<int:att_id>/download', methods=['GET'])
    def download_attachment(att_id):
        att = Attachment.query.get_or_404(att_id)
        filepath = os.path.join(app.static_folder, att.filename)
        if not os.path.exists(filepath):
            return jsonify({'error': '文件不存在'}), 404
        from flask import send_file
        return send_file(filepath, as_attachment=True, download_name=att.original_name)

    @app.route('/api/attachments/<int:att_id>', methods=['DELETE'])
    def delete_attachment(att_id):
        att = Attachment.query.get_or_404(att_id)
        filepath = os.path.join(app.static_folder, att.filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        db.session.delete(att)
        db.session.commit()
        return jsonify({'success': True, 'message': '附件已删除'})

    @app.route('/api/attachments/<int:att_id>/info', methods=['GET'])
    def get_attachment_info(att_id):
        att = Attachment.query.get_or_404(att_id)
        return jsonify(att.to_dict())

    # ==================== 头像上传 ====================
    @app.route('/api/me/avatar', methods=['POST'])
    def upload_my_avatar():
        if 'avatar' not in request.files:
            return jsonify({'error': '未选择头像文件'}), 400
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'error': '未选择头像文件'}), 400

        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp'):
            return jsonify({'error': '不支持的图片格式'}), 400

        import uuid
        from werkzeug.utils import secure_filename
        filename = f'avatar_{uuid.uuid4().hex}.{ext}'
        upload_dir = os.path.join(app.static_folder, 'avatars')
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        avatar_url = f'/static/avatars/{filename}'
        user = User.query.first()
        if user:
            user.avatar_url = avatar_url
            db.session.commit()

        return jsonify({'success': True, 'avatar_url': avatar_url})

    @app.route('/api/users/<username>/avatar', methods=['GET'])
    def get_user_avatar(username):
        user = User.query.filter_by(username=username).first()
        if not user or not user.avatar_url:
            return jsonify({'avatar_url': None}), 404
        return jsonify({'avatar_url': user.avatar_url})

    # ==================== 甘特图 API ====================
    @app.route('/api/gantt', methods=['GET'])
    def get_gantt_data():
        tasks = Task.query.order_by(Task.start_date.asc().nullslast()).all()
        # 构建依赖关系的任务ID集合（用于前端连线）
        dependency_ids = set()
        for t in tasks:
            if t.depends_on_id:
                dependency_ids.add(t.depends_on_id)
                dependency_ids.add(t.id)
        return jsonify({
            'tasks': [t.to_dict() for t in tasks],
            'dependencies': [
                {'from_id': t.depends_on_id, 'to_id': t.id}
                for t in tasks if t.depends_on_id
            ],
        })

    @app.route('/api/gantt/settings', methods=['GET'])
    def get_gantt_settings():
        tasks = Task.query.all()
        # 计算时间范围
        all_dates = []
        for t in tasks:
            if t.start_date:
                all_dates.append(t.start_date)
            if t.due_date:
                all_dates.append(t.due_date)
        return jsonify({
            'min_date': min(all_dates).isoformat() if all_dates else None,
            'max_date': max(all_dates).isoformat() if all_dates else None,
            'total_tasks': len(tasks),
        })

    # ==================== 提醒检查服务 ====================
    def check_and_create_reminders():
        """检查需要提醒的任务并生成通知（每次API请求时轻量执行）"""
        now = datetime.utcnow()
        today = now.date()
        # 只查有 due_date、有 remind_before、未完成、且尚未生成提醒的任务
        tasks_to_check = Task.query.filter(
            Task.due_date.isnot(None),
            Task.remind_before_minutes.isnot(None),
            Task.status != 'completed',
        ).all()

        created = 0
        for t in tasks_to_check:
            # 计算提醒触发时间点
            from datetime import timedelta as td
            remind_time = t.due_date - td(minutes=t.remind_before_minutes)
            # 如果提醒时间 <= 当前时间，且尚未生成提醒
            if remind_time <= today:
                # 检查是否已有该任务的提醒通知
                existing = Notification.query.filter_by(
                    task_id=t.id, ntype='reminder'
                ).first()
                if not existing:
                    days = t.remind_before_minutes // 1440
                    hours = t.remind_before_minutes // 60
                    if days > 0:
                        msg = f'任务 "{t.title}" 将在 {days} 天后到期'
                    elif hours > 0:
                        msg = f'任务 "{t.title}" 将在 {hours} 小时后到期'
                    else:
                        msg = f'任务 "{t.title}" 将在 {t.remind_before_minutes} 分钟后到期'
                    notif = Notification(task_id=t.id, message=msg, ntype='reminder')
                    db.session.add(notif)
                    created += 1
        if created:
            db.session.commit()
        return created

    @app.route('/api/notifications', methods=['GET'])
    def get_notifications():
        check_and_create_reminders()
        unread_first = Notification.query.order_by(Notification.is_read.asc(), Notification.created_at.desc()).all()
        return jsonify([n.to_dict() for n in unread_first])

    @app.route('/api/notifications/unread-count', methods=['GET'])
    def get_unread_count():
        check_and_create_reminders()
        count = Notification.query.filter_by(is_read=False).count()
        return jsonify({'count': count})

    @app.route('/api/notifications/<int:nid>/read', methods=['POST'])
    def mark_notification_read(nid):
        notif = Notification.query.get_or_404(nid)
        notif.is_read = True
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/notifications/read-all', methods=['POST'])
    def mark_all_read():
        Notification.query.filter_by(is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/notifications/<int:nid>', methods=['DELETE'])
    def delete_notification(nid):
        notif = Notification.query.get_or_404(nid)
        db.session.delete(notif)
        db.session.commit()
        return jsonify({'success': True})
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
