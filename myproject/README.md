# 团队任务管理系统

一个基于 Flask 的团队任务管理系统，支持任务创建、分配负责人和查看进度功能。

## 功能特性

- **创建任务**：用户能够创建新的任务，并填写相关信息
- **分配负责人**：每个任务可以分配给一个特定的负责人
- **查看进度**：提供界面让用户查看各个任务的完成进度
- **响应式界面**：适配桌面和移动设备
- **实时更新**：页面自动刷新任务列表和项目进度

## 技术栈

- **前端**：HTML/CSS/JavaScript + Bootstrap 5
- **后端**：Python Flask
- **数据库**：SQLite
- **部署**：Docker容器化

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行应用

```bash
python app.py
```

### 3. 访问应用

打开浏览器访问 http://localhost:5000

## API 接口

- `GET /api/tasks` - 获取所有任务
- `POST /api/tasks` - 创建新任务
- `PUT /api/tasks/<id>` - 更新任务
- `GET /api/tasks/<id>/progress` - 获取任务进度

## Docker 部署

```bash
# 构建镜像
docker build -t team-task-manager .

# 运行容器
docker run -p 5000:5000 team-task-manager
```

## 项目结构

```
myproject/
├── app.py                 # Flask 主程序
├── models.py              # 数据库模型
├── requirements.txt       # Python 依赖
├── README.md              # 项目说明
└── templates/
    └── index.html         # 前端页面
```

## 开发计划

- [x] 基础任务管理功能
- [ ] 用户认证系统
- [ ] 任务优先级设置
- [ ] 任务截止日期
- [ ] 通知系统
- [ ] 数据导出功能

## 贡献

欢迎提交 issue 和 pull request。请先讨论您想要改变的内容，然后再进行编码。