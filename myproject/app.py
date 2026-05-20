#!/usr/bin/env python3
"""团队任务管理系统 - 后端主程序"""
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from functools import wraps
from models import db, Task, User, LoginLog, Comment
import os
import time
from datetime import datetime, timedelta
import re
import hashlib


# ============================================================
# 暴力破解防护：内存存储登录失败记录
# ============================================================
class LoginRateLimiter:
    """
    简易内存登录速率限制器。
    规则：
    - 同一 identity 在 LOCKOUT_WINDOW 秒内失败 LOCKOUT_THRESHOLD 次，则锁定。
    - 锁定时长：LOCKOUT_DURATION 秒。
    """
    LOCKOUT_THRESHOLD = 5          # 连续失败次数阈值
    LOCKOUT_WINDOW = 300           # 统计窗口（秒）= 5 分钟
    LOCKOUT_DURATION = 900         # 锁定时长（秒）= 15 分钟

    def __init__(self):
        self._failures = {}  # key: identity_hash -> [(timestamp, ...)]

    def _key(self, identity: str) -> str:
        return hashlib.sha256(identity.lower().strip().encode()).hexdigest()

    def is_locked(self, identity: str) -> tuple:
        """返回 (是否锁定, 剩余锁定秒数)"""
        key = self._key(identity)
        record = self._failures.get(key, [])
        if not record:
            return False, 0
        latest_fail = record[-1]
        # 如果最近一次失败在 LOCKOUT_DURATION 内且已达到阈值
        if len(record) >= self.LOCKOUT_THRESHOLD:
            elapsed = time.time() - latest_fail
            if elapsed < self.LOCKOUT_DURATION:
                remaining = int(self.LOCKOUT_DURATION - elapsed)
                return True, remaining
            # 锁定期已过，清除记录
            self._failures[key] = []
        return False, 0

    def record_failure(self, identity: str):
        key = self._key(identity)
        now = time.time()
        record = self._failures.setdefault(key, [])
        # 清除窗口外的旧记录
        record[:] = [t for t in record if now - t < self.LOCKOUT_WINDOW]
        record.append(now)

    def clear(self, identity: str):
        key = self._key(identity)
        self._failures.pop(key, None)


rate_limiter = LoginRateLimiter()


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.permanent_session_lifetime = timedelta(hours=24)

    db.init_app(app)

    # ==================== 会话管理 ====================
    def get_current_user():
        """从会话获取当前登录用户"""
        if 'user_id' not in session:
            return None
        user = User.query.get(session['user_id'])
        if user and user.is_active:
            return user
        return None

    # ==================== 权限装饰器 ====================
    def login_required(f):
        """登录验证装饰器"""
        @wraps(f)
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user:
                # API 请求返回 JSON，页面请求重定向
                if request.path.startswith('/api/'):
                    return jsonify({'error': '未登录', 'authenticated': False}), 401
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated

    def admin_required(f):
        """管理员权限装饰器"""
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            user = get_current_user()
            if not user.is_admin:
                return jsonify({'error': '需要管理员权限'}), 403
            return f(*args, **kwargs)
        return decorated

    def role_required(*roles):
        """角色权限装饰器"""
        def decorator(f):
            @wraps(f)
            @login_required
            def decorated(*args, **kwargs):
                user = get_current_user()
                if user.role not in roles:
                    return jsonify({'error': '权限不足'}), 403
                return f(*args, **kwargs)
            return decorated
        return decorator

    # ==================== 登录日志 ====================
    def log_login_attempt(user=None, username_attempted=None, success=False, 
                         failure_reason=None, login_method='password'):
        """记录登录尝试"""
        log = LoginLog(
            user_id=user.id if user else None,
            username_attempted=username_attempted,
            ip_address=request.remote_addr or 'unknown',
            user_agent=request.headers.get('User-Agent', '')[:500],
            success=success,
            failure_reason=failure_reason,
            login_method=login_method,
            created_at=datetime.utcnow()
        )
        db.session.add(log)
        db.session.commit()

    # ==================== 数据库初始化 ====================
    with app.app_context():
        db.create_all()

        # 创建默认管理员账户（仅在首次运行时）
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@example.com',
                role='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()

    # ==================== 页面路由 ====================
    @app.route('/')
    def index():
        # 首页对所有人开放，但根据登录状态显示不同内容
        user = get_current_user()
        return render_template('index.html', user=user)

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            data = request.get_json() or {}
            identity = (data.get('identity') or '').strip()
            password = data.get('password', '')
            remember_me = data.get('remember_me', False)

            # 基础校验
            if not identity or not password:
                log_login_attempt(username_attempted=identity, success=False, 
                                failure_reason='missing_fields', login_method='password')
                return jsonify({'success': False, 'message': '请输入账号和密码'}), 400

            # 检查是否被锁定
            locked, remaining = rate_limiter.is_locked(identity)
            if locked:
                log_login_attempt(username_attempted=identity, success=False, 
                                failure_reason='rate_limited', login_method='password')
                return jsonify({
                    'success': False,
                    'message': f'登录失败次数过多，请 {remaining} 秒后再试',
                    'lockout_time': remaining
                }), 429

            # 查找用户（支持用户名/邮箱/手机号）
            user = User.find_by_identity(identity)

            if user and user.check_password(password) and user.is_active:
                # 登录成功：清除失败记录
                rate_limiter.clear(identity)

                # 更新最后登录时间
                user.last_login = datetime.utcnow()
                db.session.commit()

                # 记录成功登录
                log_login_attempt(user=user, success=True, login_method='password')

                session.permanent = remember_me
                session['user_id'] = user.id
                session['username'] = user.username
                session['user_role'] = user.role
                session['login_time'] = datetime.utcnow().isoformat()
                session['login_ip'] = request.remote_addr

                return jsonify({
                    'success': True,
                    'message': '登录成功',
                    'user': user.to_dict()
                })
            else:
                # 登录失败：记录
                rate_limiter.record_failure(identity)
                log_login_attempt(username_attempted=identity, success=False, 
                                failure_reason='invalid_credentials', login_method='password')
                _, remaining = rate_limiter.is_locked(identity)
                if remaining > 0:
                    return jsonify({
                        'success': False,
                        'message': f'登录失败次数过多，请 {remaining} 秒后再试',
                        'lockout_time': remaining
                    }), 429
                return jsonify({'success': False, 'message': '账号或密码错误'}), 401

        # GET
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            data = request.get_json() or {}
            username = (data.get('username') or '').strip()
            password = (data.get('password') or '').strip()
            email = (data.get('email') or '').strip().lower()
            confirm_password = (data.get('confirm_password') or data.get('confirmPassword') or '').strip()
            phone = (data.get('phone') or '').strip()

            # 必填字段
            if not username or not password or not email:
                return jsonify({'success': False, 'message': '用户名、密码和邮箱不能为空'}), 400

            # 密码确认
            if password != confirm_password:
                return jsonify({'success': False, 'message': '两次输入的密码不一致'}), 400

            # 用户名长度
            if len(username) < 3 or len(username) > 20:
                return jsonify({'success': False, 'message': '用户名长度必须在3-20个字符之间'}), 400

            # 密码强度
            if len(password) < 6:
                return jsonify({'success': False, 'message': '密码长度至少6位'}), 400

            # 邮箱格式
            if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400

            # 手机号格式（如果提供）
            if phone and not re.match(r'^1[3-9]\d{9}$', phone):
                return jsonify({'success': False, 'message': '手机号格式不正确'}), 400

            # 用户名唯一
            if User.query.filter_by(username=username).first():
                return jsonify({'success': False, 'message': '用户名已存在'}), 400

            # 邮箱唯一
            if User.query.filter_by(email=email).first():
                return jsonify({'success': False, 'message': '邮箱已被使用'}), 400

            # 手机号唯一
            if phone and User.query.filter_by(phone=phone).first():
                return jsonify({'success': False, 'message': '手机号已被使用'}), 400

            try:
                new_user = User(
                    username=username,
                    email=email,
                    phone=phone or None,
                    role='user'
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                # 注册成功后自动登录（commit 之后 new_user.id 才生效）
                session["user_id"] = new_user.id
                session["username"] = new_user.username
                session["user_role"] = new_user.role
                session["login_time"] = datetime.utcnow().isoformat()
                session["login_ip"] = request.remote_addr

                return jsonify({
                    'success': True,
                    'message': '用户注册成功',
                    'user': new_user.to_dict()
                }), 201
            except Exception:
                db.session.rollback()
                return jsonify({'success': False, 'message': '注册失败，请稍后重试'}), 500

        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('register.html')

    @app.route('/logout')
    def logout():
        # 记录登出时间
        user = get_current_user()
        if user:
            user.last_login = datetime.utcnow()
            db.session.commit()
        
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('user_role', None)
        session.pop('login_time', None)
        session.pop('login_ip', None)
        return redirect(url_for('index'))

    # ==================== OAuth 路由 ====================
    @app.route('/auth/<provider>')
    def oauth_login(provider):
        """OAuth 登录入口"""
        if provider not in ['github', 'wechat', 'qq']:
            return jsonify({'error': '不支持的登录方式'}), 400
        
        # 这里应该重定向到对应的 OAuth 提供商
        # 示例：return redirect(get_oauth_authorize_url(provider))
        return jsonify({'message': f'{provider} OAuth 登录功能待实现'}), 200

    @app.route('/auth/<provider>/callback')
    def oauth_callback(provider):
        """OAuth 回调处理"""
        if provider not in ['github', 'wechat', 'qq']:
            return jsonify({'error': '不支持的登录方式'}), 400
            
        # 这里应该处理 OAuth 回调，获取用户信息并登录
        # 示例：user_info = get_oauth_user_info(provider, request.args.get('code'))
        #       user = create_or_find_user_from_oauth(provider, user_info)
        #       login_user(user)
        return jsonify({'message': f'{provider} OAuth 回调处理功能待实现'}), 200

    # ==================== API 路由 ====================
    @app.route('/api/check-session')
    def check_session():
        """检查当前会话状态"""
        user = get_current_user()
        if user:
            return jsonify({
                'authenticated': True,
                'user': user.to_dict(full=True)
            })
        return jsonify({'authenticated': False, 'user': None}), 401

    @app.route('/api/profile', methods=['GET', 'PUT'])
    @login_required
    def profile():
        """查看/更新个人资料（用户名、邮箱、手机号、头像、密码）"""
        user = get_current_user()
        if request.method == 'PUT':
            data = request.get_json() or {}

            # ---- 修改用户名 ----
            if 'username' in data:
                new_username = data['username'].strip()
                if len(new_username) < 3 or len(new_username) > 20:
                    return jsonify({'success': False, 'message': '用户名长度必须在3-20个字符之间'}), 400
                existing = User.query.filter(User.username == new_username, User.id != user.id).first()
                if existing:
                    return jsonify({'success': False, 'message': '用户名已被使用'}), 400
                user.username = new_username
                # 同步更新 session 中的用户名
                session['username'] = new_username

            # ---- 修改邮箱 ----
            if 'email' in data:
                email = data['email'].strip().lower()
                if email == '':
                    return jsonify({'success': False, 'message': '邮箱不能为空'}), 400
                if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                    return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400
                existing = User.query.filter(User.email == email, User.id != user.id).first()
                if existing:
                    return jsonify({'success': False, 'message': '邮箱已被使用'}), 400
                user.email = email

            # ---- 修改手机号 ----
            if 'phone' in data:
                phone = data['phone'].strip()
                if phone and not re.match(r'^1[3-9]\d{9}$', phone):
                    return jsonify({'success': False, 'message': '手机号格式不正确'}), 400
                if phone:
                    existing = User.query.filter(User.phone == phone, User.id != user.id).first()
                    if existing:
                        return jsonify({'success': False, 'message': '手机号已被使用'}), 400
                    user.phone = phone
                else:
                    user.phone = None  # 允许清空手机号

            # ---- 修改头像URL ----
            if 'avatar_url' in data:
                avatar_url = data['avatar_url'].strip()
                if avatar_url and not (avatar_url.startswith('http://') or avatar_url.startswith('https://') or avatar_url.startswith('/')):
                    return jsonify({'success': False, 'message': '头像URL格式不正确'}), 400
                user.avatar_url = avatar_url if avatar_url else None

            # ---- 修改密码 ----
            if 'password' in data and data['password']:
                if len(data['password']) < 6:
                    return jsonify({'success': False, 'message': '密码长度至少6位'}), 400
                user.set_password(data['password'])

            db.session.commit()
            return jsonify({'success': True, 'user': user.to_dict(full=True)})

        # GET —— 返回完整用户信息
        return jsonify({'success': True, 'user': user.to_dict(full=True)})

    @app.route('/api/profile/avatar', methods=['POST'])
    @login_required
    def upload_avatar():
        """上传头像文件"""
        user = get_current_user()

        if 'avatar' not in request.files:
            return jsonify({'success': False, 'message': '未选择头像文件'}), 400

        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'message': '未选择头像文件'}), 400

        # 校验文件类型
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'message': f'不支持的图片格式，仅支持: {", ".join(allowed_extensions)}'
            }), 400

        # 校验文件大小（最大 5MB）
        file_size = len(file.read())
        file.seek(0)
        if file_size > 5 * 1024 * 1024:
            return jsonify({'success': False, 'message': '头像文件大小不能超过5MB'}), 400

        # 生成文件路径
        upload_dir = os.path.join(app.root_path, 'static', 'avatars')
        os.makedirs(upload_dir, exist_ok=True)

        safe_filename = f'user_{user.id}_{int(time.time())}.{ext}'
        file_path = os.path.join(upload_dir, safe_filename)
        file.save(file_path)

        # 更新用户头像 URL
        avatar_url = f'/static/avatars/{safe_filename}'
        user.avatar_url = avatar_url
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '头像上传成功',
            'avatar_url': avatar_url,
            'user': user.to_dict(full=True)
        })

    @app.route('/api/users', methods=['GET'])
    @admin_required
    def list_users():
        """管理员：列出所有用户"""
        users = User.query.all()
        return jsonify([u.to_dict(full=True) for u in users])

    @app.route('/api/tasks', methods=['GET'])
    @login_required
    def get_tasks():
        tasks = Task.query.all()
        return jsonify([{
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'assignee': task.assignee,
            'status': task.status,
            'created_at': task.created_at.isoformat()
        } for task in tasks])

    @app.route('/api/tasks', methods=['POST'])
    @role_required('admin', 'user')
    def create_task():
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({'error': '标题不能为空'}), 400

        task = Task(
            title=data['title'],
            description=data.get('description', ''),
            assignee=data.get('assignee', ''),
            status=data.get('status', 'pending')
        )
        db.session.add(task)
        db.session.commit()

        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'assignee': task.assignee,
            'status': task.status,
            'created_at': task.created_at.isoformat()
        }), 201

    @app.route('/api/tasks/<int:task_id>', methods=['PUT'])
    @login_required
    def update_task(task_id):
        task = Task.query.get_or_404(task_id)
        data = request.get_json()

        task.title = data.get('title', task.title)
        task.description = data.get('description', task.description)
        task.assignee = data.get('assignee', task.assignee)
        task.status = data.get('status', task.status)

        db.session.commit()

        return jsonify({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'assignee': task.assignee,
            'status': task.status,
            'created_at': task.created_at.isoformat()
        })

    @app.route('/api/tasks/<int:task_id>/progress', methods=['GET'])
    @login_required
    def get_task_progress(task_id):
        task = Task.query.get_or_404(task_id)
        total_tasks = Task.query.count()
        completed_tasks = Task.query.filter_by(status='completed').count()

        return jsonify({
            'task_id': task.id,
            'status': task.status,
            'progress': {
                'total': total_tasks,
                'completed': completed_tasks,
                'percentage': (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            }
        })



    @app.route('/api/tasks/<int:task_id>/comments', methods=['GET'])
    @login_required
    def get_task_comments(task_id):
        """获取任务的所有评论"""
        task = Task.query.get_or_404(task_id)
        comments = Comment.query.filter_by(task_id=task.id, is_deleted=False).order_by(Comment.created_at.asc()).all()
        return jsonify([c.to_dict() for c in comments])

    @app.route('/api/tasks/<int:task_id>/comments', methods=['POST'])
    @login_required
    def create_comment(task_id):
        """发表评论"""
        task = Task.query.get_or_404(task_id)
        user = get_current_user()
        data = request.get_json() or {}

        content_text = (data.get('content') or '').strip()
        if not content_text:
            return jsonify({'error': '评论内容不能为空'}), 400

        if len(content_text) > 5000:
            return jsonify({'error': '评论内容不能超过5000字符'}), 400

        comment = Comment(
            task_id=task.id,
            user_id=user.id,
            content=content_text,
        )
        db.session.add(comment)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '评论发表成功',
            'comment': comment.to_dict()
        }), 201

    @app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
    @login_required
    def delete_comment(comment_id):
        """删除评论（仅评论作者或管理员可删除）"""
        comment = Comment.query.get_or_404(comment_id)
        user = get_current_user()

        if comment.user_id != user.id and not user.is_admin:
            return jsonify({'error': '无权删除此评论'}), 403

        # 软删除
        comment.is_deleted = True
        comment.content = ''
        db.session.commit()

        return jsonify({'success': True, 'message': '评论已删除'})
    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
