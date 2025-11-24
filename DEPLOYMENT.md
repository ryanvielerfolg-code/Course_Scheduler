# Deployment Guide - Course Scheduler

This project supports deployment on multiple free cloud platforms. Below are deployment instructions for each platform:

## 🚀 Recommended Platforms (in order of recommendation)

### 1. **Render** ⭐ Most Recommended
- **Free Quota**: 750 hours/month
- **Advantages**: Simple to use, automatic deployment, supports Flask
- **Deployment Steps**:
  1. Visit https://render.com
  2. Register/Log in to your account
  3. Click “New +” → “Web Service”
  4. Connect your GitHub repository
  5. Configure:
     - **Name**: course-scheduler
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python app.py`
  6. Click “Create Web Service”
  7. Wait for deployment to complete (approx. 5-10 minutes)

### 2. **Railway** ⭐ Also Highly Recommended
- **Free Tier**: $5/month free credit
- **Advantages**: Fast deployment, supports multiple languages
- **Deployment Steps**:
  1. Visit https://railway.app
  2. Register/Log in (GitHub login supported)
  3. Click “New Project”
  4. Select “Deploy from GitHub repo”
  5. Choose your repository
  6. Railway automatically detects Python projects and deploys
  7. Wait for deployment to complete

### 3. **Fly.io**
- **Free Tier**: 3 shared CPUs, 256MB RAM
- **Advantages**: Global edge deployment, fast speeds
- **Deployment Steps**:
  1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
  2. Log in: `fly auth login`
  3. Run in project directory: `fly launch`
  4. Follow prompts to complete configuration

### 4. **PythonAnywhere**
- **Free Tier**: 1 web application
- **Advantages**: Designed specifically for Python
- **Deployment Steps**:
  1. Visit https://www.pythonanywhere.com
  2. Sign up for a free account
  3. Upload code files
  4. Configure the web application

## 📋 Pre-Deployment Checklist

- [x] `requirements.txt` includes all dependencies
- [x] `app.py` configures the correct port (read from environment variables)
- [x] `Procfile` created (required for some platforms)
- [x] All necessary files are on GitHub

## 🔧 Environment Variable Configuration

Some platforms may require setting environment variables:
- `PORT`: Server port (usually set automatically by the platform)

## 📝 Important Notes

1. **File size limits**: Ensure uploaded files do not exceed platform restrictions
2. **Execution time limits**: Free tiers often have execution time caps (e.g., 30 or 60 seconds)
3. **Storage limitations**: Temporary files are cleaned up after request completion
4. **Dependency installation**: Initial deployments may take longer due to dependency setup



Translated with DeepL.com (free version)
