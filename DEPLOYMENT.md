# 🚀 Drift Coach 极速部署指南

**目标**：无 VPS、无备案、无运维的前提下，最快上线可访问 Demo

- **后端**: FastAPI → Railway
- **前端**: React/Vite → Vercel
- **部署时间**: 约 10 分钟

---

## 📋 部署前准备

确保你已有：
- ✅ GitHub 账号
- ✅ 本项目已推送到 GitHub
- ✅ Railway 和 Vercel 账号（用 GitHub 登录即可）

---

## 一、后端部署（Railway）⚡

### 1️⃣ 创建 Railway 项目

1. 打开 https://railway.app
2. 使用 **GitHub 登录**
3. 点击 **New Project** → **Deploy from GitHub repo**
4. 选择 `DriftCoach-Backend-for-cloud9-hackthon-` 仓库

### 2️⃣ Railway 自动识别

Railway 会自动检测到：
- ✅ `requirements.txt` (Python 依赖)
- ✅ `Procfile` (启动命令)
- ✅ `driftcoach/api.py` (FastAPI 应用)

**无需任何额外配置**，Railway 会自动构建！

### 3️⃣ 设置环境变量 ⚙️

在 Railway 项目中：
1. 点击项目 → **Variables** 标签
2. 添加以下环境变量：

```bash
DATA_SOURCE=grid
GRID_API_KEY=V7gRAqatBVwdMb8lGKi5st9RtFMUhKwSwxuRWObv
GRID_SERIES_ID=2819676
GRID_PLAYER_ID=91
CORS_ALLOW_ORIGINS=*
```

⚠️ **必须全部填写**，否则后端无法启动！

### 4️⃣ 获取后端 URL

部署成功后，Railway 会生成一个 URL，格式类似：

```
https://driftcoach-backend-production.up.railway.app
```

**验证后端是否运行**：

```bash
curl https://<你的railway-url>/api/demo
```

应该返回 `200 OK` 和 JSON 数据。

---

## 二、前端部署（Vercel）🎨

### 1️⃣ 配置前端环境变量

在 `frontend` 目录下创建 `.env` 文件：

```bash
VITE_API_BASE=https://<你的railway-url>/api
```

⚠️ 替换 `<你的railway-url>` 为上一步 Railway 给你的 URL

### 2️⃣ 推送代码到 GitHub

```bash
git add .
git commit -m "Add Railway & Vercel deployment config"
git push
```

### 3️⃣ Vercel 部署

1. 打开 https://vercel.com
2. 使用 **GitHub 登录**
3. 点击 **Import Project**
4. 选择 `DriftCoach-Backend-for-cloud9-hackthon-` 仓库
5. 配置如下：

**Root Directory**: `frontend`  
**Build Command**: `npm run build`  
**Output Directory**: `dist`

### 4️⃣ 添加 Vercel 环境变量

在 Vercel 项目设置中：
1. 进入 **Settings** → **Environment Variables**
2. 添加：

```bash
VITE_API_BASE=https://<你的railway-url>/api
```

3. 点击 **Redeploy** 重新部署

---

## 三、验收测试 ✅

打开 Vercel 给你的前端 URL（类似 `https://driftcoach.vercel.app`），测试以下问题：

### 测试问题：

1. **请给这场比赛的复盘议程**
2. **这场比赛的经济管理问题在哪里？**
3. **这是不是一场高风险对局？**
4. **请总结这场比赛的关键教训**

### 要求：
- ✅ 页面不崩溃
- ✅ 不进入安全模式
- ✅ 不同问题给出不同答案

---

## 四、交付清单 📦

完成后，你将获得：

1. ✅ **后端 URL** (Railway): `https://<your-app>.up.railway.app`
2. ✅ **前端 URL** (Vercel): `https://<your-app>.vercel.app`
3. ✅ **Demo 状态**: 已在浏览器完整跑通

---

## 🔧 常见问题

### Railway 被限流怎么办？

**Plan B** (次快选择)：
- [Render](https://render.com) - 免费但部署较慢
- [Fly.io](https://fly.io) - 稳定但需要信用卡验证

### Vercel 部署失败？

检查：
1. `frontend/package.json` 中是否有 `build` 脚本
2. `VITE_API_BASE` 是否正确设置
3. 尝试重新部署

### API 返回 CORS 错误？

确保 Railway 环境变量中设置了：
```bash
CORS_ALLOW_ORIGINS=*
```

---

## 📝 项目文件说明

已为你创建以下部署文件：

- `Procfile` - Railway 启动命令
- `.env.example` - 后端环境变量模板
- `frontend/.env.example` - 前端环境变量模板
- `requirements.txt` - Python 依赖（已更新）

---

## ⚡ 约束条件

- ❌ 不做性能优化
- ❌ 不上 Docker/VPS
- ❌ 不重构架构
- ✅ **只保证 Demo 可访问、可演示**

---

## 🎯 下一步

1. **立即部署后端** → Railway
2. **立即部署前端** → Vercel
3. **测试 Demo** → 浏览器验证
4. **交付链接** → 给项目负责人

**预计总时间**: 10-15 分钟

Good luck! 🚀
