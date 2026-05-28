# 自动适配你的项目结构
try:
    from app import db, application
    app = application
except:
    from app import db, app

with app.app_context():
    db.create_all()
    print("✅ 数据库表创建成功！")
