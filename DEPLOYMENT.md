# 部署指南 - Course Scheduler

本项目支持多个免费云平台部署。以下是各平台的部署说明：

## 🚀 推荐平台（按推荐顺序）

### 1. **Render** ⭐ 最推荐
- **免费额度**: 750 小时/月
- **优点**: 简单易用，自动部署，支持 Flask
- **部署步骤**:
  1. 访问 https://render.com
  2. 注册/登录账户
  3. 点击 "New +" → "Web Service"
  4. 连接 GitHub 仓库
  5. 配置：
     - **Name**: course-scheduler
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python app.py`
  6. 点击 "Create Web Service"
  7. 等待部署完成（约 5-10 分钟）

### 2. **Railway** ⭐ 也很推荐
- **免费额度**: $5/月免费额度
- **优点**: 部署快速，支持多种语言
- **部署步骤**:
  1. 访问 https://railway.app
  2. 注册/登录账户（可使用 GitHub 登录）
  3. 点击 "New Project"
  4. 选择 "Deploy from GitHub repo"
  5. 选择您的仓库
  6. Railway 会自动检测 Python 项目并部署
  7. 等待部署完成

### 3. **Fly.io**
- **免费额度**: 3 个共享 CPU，256MB RAM
- **优点**: 全球边缘部署，速度快
- **部署步骤**:
  1. 安装 Fly CLI: `curl -L https://fly.io/install.sh | sh`
  2. 登录: `fly auth login`
  3. 在项目目录运行: `fly launch`
  4. 按照提示完成配置

### 4. **PythonAnywhere**
- **免费额度**: 1 个 Web 应用
- **优点**: 专为 Python 设计
- **部署步骤**:
  1. 访问 https://www.pythonanywhere.com
  2. 注册免费账户
  3. 上传代码文件
  4. 配置 Web 应用

## 📋 部署前检查清单

- [x] `requirements.txt` 包含所有依赖
- [x] `app.py` 配置了正确的端口（从环境变量读取）
- [x] `Procfile` 已创建（用于某些平台）
- [x] 所有必要的文件都在 GitHub 上

## 🔧 环境变量配置

某些平台可能需要设置环境变量：
- `PORT`: 服务器端口（通常平台会自动设置）

## 📝 注意事项

1. **文件大小限制**: 确保上传的文件不超过平台限制
2. **执行时间限制**: 免费 tier 通常有执行时间限制（如 30 秒或 60 秒）
3. **存储限制**: 临时文件会在请求结束后清理
4. **依赖安装**: 首次部署可能需要较长时间安装依赖

## 🐛 常见问题

### 问题：部署后出现 404 错误
- 检查路由配置是否正确
- 确认 `app.py` 中的路由路径

### 问题：依赖安装失败
- 检查 `requirements.txt` 中的包版本是否兼容
- 某些平台可能需要指定 Python 版本

### 问题：超时错误
- 免费 tier 通常有执行时间限制
- 考虑优化代码或升级到付费 tier

## 🎯 推荐选择

**对于初学者**: 推荐使用 **Render**，界面友好，配置简单。

**对于需要更多控制**: 推荐使用 **Railway**，功能强大，部署快速。

