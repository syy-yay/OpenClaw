#!/usr/bin/env python3
"""团队任务管理系统 - 后端主程序（开放访问版）"""
from flask import Flask, request, jsonify, render_template
from models import db, Task, User, Tag, task_tags, Comment, Note
import os
from datetime import datetime, timedelta, date
import re


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    db.init_app(app)

    # ==================== 数据库初始化 ====================
    with app.app_context():
        db.create_all()

    # ==================== 页面路由 ====================
    @app.route('/')
    def index():
        return render_template('index.html')

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
