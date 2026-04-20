#!/usr/bin/env python3
from flask import Flask, request, jsonify, render_template
from models import db, Task
import os

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///tasks.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # 初始化数据库
    db.init_app(app)
    
    with app.app_context():
        db.create_all()
    
    @app.route('/')
    def index():
        return render_template('index.html')
    
    @app.route('/api/tasks', methods=['GET'])
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
    def create_task():
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
    app.run(debug=True, host='0.0.0.0', port=5000)