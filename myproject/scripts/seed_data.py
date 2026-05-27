#!/usr/bin/env python3
"""种子数据生成脚本 - 创建示例任务用于测试和演示"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, Task, User, Tag, Comment, Note
from datetime import date, timedelta, datetime
import random

app = create_app()

SAMPLE_TASKS = [
    # (标题, 描述, 状态, 优先级, 负责人, 距今天截止天数, 持续天数, 进度%)
    ("完成项目需求文档", "编写完整的项目需求规格说明书，包含功能需求和非功能需求", "completed", "high", "张三", -10, 5, 100),
    ("设计数据库模型", "设计系统核心数据表结构，包括用户、任务、标签、评论等模块", "completed", "high", "李四", -7, 3, 100),
    ("实现用户注册功能", "开发用户注册接口，包含前端页面和后端API，支持邮箱验证", "completed", "high", "王五", -5, 4, 100),
    ("实现用户登录功能", "开发用户登录接口，支持用户名/邮箱/手机号登录，集成JWT认证", "completed", "medium", "张三", -3, 3, 100),
    ("部署测试环境", "配置Docker容器和Kubernetes部署文件，搭建CI/CD流水线", "completed", "low", "李四", -2, 2, 100),
    ("修复登录页面样式问题", "登录页面在移动端显示异常，需要修复响应式布局", "in-progress", "high", "王五", 1, 2, 60),
    ("开发任务管理页面", "实现任务的增删改查功能，包括列表展示、搜索、分页", "in-progress", "high", "张三", 3, 7, 45),
    ("实现任务标签功能", "开发任务标签的创建、关联、筛选功能，支持多对多关系", "in-progress", "medium", "李四", 5, 4, 30),
    ("添加文件上传功能", "支持在任务中添加附件，包括文件上传、下载和删除", "in-progress", "medium", "王五", 7, 5, 15),
    ("编写单元测试", "为核心业务逻辑编写单元测试，覆盖率达到80%以上", "pending", "high", "张三", 2, 5, 0),
    ("实现消息通知功能", "开发站内消息通知系统，支持任务提醒和系统消息", "pending", "high", "李四", 4, 6, 0),
    ("优化数据库查询性能", "分析慢查询并添加索引，优化列表页加载速度", "pending", "medium", "王五", 6, 3, 0),
    ("添加操作日志功能", "记录用户关键操作，支持操作审计和追溯", "pending", "medium", "张三", 8, 4, 0),
    ("实现数据导出功能", "支持将任务数据导出为Excel和CSV格式", "pending", "low", "李四", 10, 3, 0),
    ("性能压测和调优", "使用JMeter进行压力测试，优化系统吞吐量和响应时间", "pending", "low", "王五", 14, 5, 0),
    ("修复搜索功能Bug", "搜索关键词包含特殊字符时导致500错误", "pending", "high", "张三", 1, 1, 0),
    ("添加国际化支持", "前端支持中英文切换，后端返回多语言错误信息", "pending", "low", "李四", 20, 10, 0),
    ("开发甘特图视图", "实现任务甘特图展示，支持按时间线查看任务进度", "pending", "medium", "王五", 12, 5, 0),
    ("集成第三方登录", "支持GitHub和微信OAuth登录", "pending", "low", "张三", 30, 7, 0),
    ("系统安全审计", "检查CSRF、XSS、SQL注入等安全漏洞并修复", "pending", "high", "李四", 15, 4, 0),
    ("首页数据统计面板", "开发仪表盘页面，展示任务统计数据和进度图表", "pending", "medium", "王五", 9, 3, 0),
    ("添加夜间模式", "前端支持暗色主题切换", "pending", "low", "张三", 25, 3, 0),
    ("实现任务评论功能", "支持在任务详情页添加评论和回复", "completed", "high", "李四", -4, 3, 100),
    ("添加截止日期功能", "任务支持设置截止日期并显示剩余天数", "completed", "medium", "王五", -1, 2, 100),
    ("任务超期自动提醒", "对即将到期或已超期任务发送站内通知", "in-progress", "high", "张三", 2, 3, 50),
    ("API文档生成", "使用Swagger自动生成API文档", "pending", "low", "李四", 18, 2, 0),
]


def run():
    with app.app_context():
        db.create_all()

        # 确保有用户
        users = []
        for name in ['张三', '李四', '王五']:
            u = User.query.filter_by(username=name).first()
            if not u:
                u = User(username=name, email=f'{name}@example.com')
                u.set_password('123456')
                db.session.add(u)
            users.append(u)
        db.session.commit()
        print(f"✅ 确认了 {len(users)} 个用户")

        # 创建标签
        tags_data = [
            ('bug', '#dc3545'), ('feature', '#28a745'),
            ('urgent', '#fd7e14'), ('documentation', '#17a2b8'),
            ('enhancement', '#6f42c1'),
        ]
        tags = []
        for name, color in tags_data:
            if not Tag.query.filter_by(name=name).first():
                t = Tag(name=name, color=color)
                db.session.add(t)
                tags.append(t)
            else:
                tags.append(Tag.query.filter_by(name=name).first())
        db.session.commit()
        print(f"✅ 创建了 {len(tags)} 个标签")

        # 创建任务
        from models import task_tags
        db.session.execute(task_tags.delete())
        Comment.query.delete()
        Note.query.delete()
        Task.query.delete()
        db.session.commit()

        created = 0
        for title, desc, status, priority, assignee, due_offset, duration, progress in SAMPLE_TASKS:
            due = date.today() + timedelta(days=due_offset) if due_offset else None
            start = due - timedelta(days=duration) if due else date.today() - timedelta(days=random.randint(1, 10))

            task = Task(
                title=title,
                description=desc,
                assignee=assignee,
                status=status,
                priority=priority,
                due_date=due,
                start_date=start,
                duration_days=duration,
                progress_pct=progress,
            )
            db.session.add(task)
            db.session.flush()

            # 随机关联 1-2 个标签
            task_tags = random.sample(tags, random.randint(1, 2))
            for t in task_tags:
                task.tags.append(t)

            # 已完成任务添加评论和备注
            if status == 'completed':
                c = Comment(task_id=task.id, user_id=random.choice(users).id,
                           content=f'{title} 已完成，测试通过。')
                db.session.add(c)
                n = Note(task_id=task.id, user_id=random.choice(users).id,
                        content=f'验收记录：{title} 功能正常，文档已更新。')
                db.session.add(n)

            created += 1

        db.session.commit()

        # 统计数据
        status_counts = {}
        priority_counts = {}
        for s in ['pending', 'in-progress', 'completed']:
            status_counts[s] = Task.query.filter_by(status=s).count()
        for p in ['high', 'medium', 'low']:
            priority_counts[p] = Task.query.filter_by(priority=p).count()

        print(f"\n✅ 生成了 {created} 个示例任务")
        print(f"   📊 状态分布: {status_counts}")
        print(f"   📊 优先级分布: {priority_counts}")
        print(f"   🏷️ 标签: {len(tags)} 个")
        print(f"   👥 用户: {len(users)} 个")
        print(f"\n💡 管理员账号: admin / admin123")
        print(f"💡 测试用户: 张三 / 123456")


if __name__ == '__main__':
    run()
