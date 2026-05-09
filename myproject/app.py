#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from models import db, Task, User
import os
from datetime import datetime, timedelta
import re

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # 在生产环境中应该从环境变量读取密钥
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # 会话配置
    app.permanent_session_lifetime = timedelta(hours=24)  # 会话持续24小时
    
    # 初始化数据库
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
        
        # 创建默认管理员账户（仅在首次运行时）
        if not User.query.filter_by(username='admin').first():
            admin_user = User(username='admin', email='admin@example.com')
            admin_user.set_password('admin123')  # 默认密码
            db.session.add(admin_user)
            db.session.commit()
    
    @app.route('/')
    def index():
        # 检查用户是否已登录
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return render_template('index.html')
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            remember_me = data.get('remember_me', False)
            
            # 防止暴力破解：添加简单的速率限制检查
            # 这里可以扩展为实际的速率限制机制
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password) and user.is_active:
                session.permanent = remember_me  # 如果用户选择了"记住我"，则延长会话时间
                session['user_id'] = user.id
                session['username'] = user.username
                session['login_time'] = datetime.now().isoformat()
                
                return jsonify({
                    'success': True, 
                    'message': '登录成功',
                    'user': {
                        'id': user.id,
                        'username': user.username
                    }
                })
            else:
                return jsonify({'success': False, 'message': '用户名或密码错误'})
        
        # GET请求返回登录页面
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('login.html')
    
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            email = data.get('email', '')
            
            # 输入验证
            if not username or not password:
                return jsonify({'success': False, 'message': '用户名和密码不能为空'})
            
            if len(username) < 3 or len(username) > 20:
                return jsonify({'success': False, 'message': '用户名长度必须在3-20个字符之间'})
            
            if len(password) < 6:
                return jsonify({'success': False, 'message': '密码长度至少6位'})
            
            # 验证邮箱格式（如果提供了邮箱）
            if email and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return jsonify({'success': False, 'message': '邮箱格式不正确'})
            
            # 检查用户名是否已存在
            if User.query.filter_by(username=username).first():
                return jsonify({'success': False, 'message': '用户名已存在'})
            
            # 检查邮箱是否已存在（如果提供了邮箱）
            if email and User.query.filter_by(email=email).first():
                return jsonify({'success': False, 'message': '邮箱已被使用'})
            
            # 创建新用户
            try:
                new_user = User(username=username, email=email)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                
                return jsonify({
                    'success': True, 
                    'message': '用户注册成功',
                    'user': {
                        'id': new_user.id,
                        'username': new_user.username,
                        'email': new_user.email
                    }
                })
            except Exception as e:
                db.session.rollback()
                return jsonify({'success': False, 'message': '注册失败，请稍后重试'})
        
        # GET请求返回注册页面
        if 'user_id' in session:
            return redirect(url_for('index'))
        return render_template('register.html')
    
    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        session.pop('username', None)
        session.pop('login_time', None)
        return redirect(url_for('login'))
    
    @app.route('/api/check-session')
    def check_session():
        """检查当前会话状态"""
        if 'user_id' in session:
            user = User.query.get(session['user_id'])
            if user and user.is_active:
                return jsonify({
                    'authenticated': True,
                    'user': {
                        'id': user.id,
                        'username': user.username
                    }
                })
        return jsonify({'authenticated': False}), 401
    
    @app.route('/api/tasks', methods=['GET'])
    def get_tasks():
        # 检查用户是否已登录
        if 'user_id' not in session:
            return jsonify({'error': '未授权访问'}), 401
            
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
    def create_task():
        # 检查用户是否已登录
        if 'user_id' not in session:
            return jsonify({'error': '未授权访问'}), 401
            
        data = request.get_json()
        
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
    def update_task(task_id):
        # 检查用户是否已登录
        if 'user_id' not in session:
            return jsonify({'error': '未授权访问'}), 401
            
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
    def get_task_progress(task_id):
        # 检查用户是否已登录
        if 'user_id' not in session:
            return jsonify({'error': '未授权访问'}), 401
            
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
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5001)  # 更改为端口5001