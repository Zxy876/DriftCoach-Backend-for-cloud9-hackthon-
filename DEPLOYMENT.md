# 🚀 Drift Coach Fast Deployment Guide

**Goal**: Ship an accessible demo as fast as possible with no VPS, no ICP filing, and no ops overhead.

- **Backend**: FastAPI → Railway
- **Frontend**: React/Vite → Vercel
- **Time**: ~10 minutes

---

## 📋 Prerequisites

Make sure you have:
- ✅ GitHub account
- ✅ This project pushed to GitHub
- ✅ Railway and Vercel accounts (sign in with GitHub)

---

## I. Backend on Railway ⚡

### 1️⃣ Create a Railway project

1. Visit https://railway.app
2. Sign in with **GitHub**
3. Click **New Project** → **Deploy from GitHub repo**
4. Select the `DriftCoach-Backend-for-cloud9-hackthon-` repo

### 2️⃣ Auto-detection

Railway will auto-detect:
- ✅ `requirements.txt` (Python deps)
- ✅ `Procfile` (start command)
- ✅ `driftcoach/api.py` (FastAPI app)

No extra config needed—Railway builds automatically.

### 3️⃣ Set environment variables ⚙️

In the Railway project:
1. Open project → **Variables** tab
2. Add the following variables:

```bash
DATA_SOURCE=grid
GRID_API_KEY=V7gRAqatBVwdMb8lGKi5st9RtFMUhKwSwxuRWObv
GRID_SERIES_ID=2819676
GRID_PLAYER_ID=91
CORS_ALLOW_ORIGINS=*
```

⚠️ **Fill all of them** or the backend will not start.

### 4️⃣ Get backend URL

After deploy, Railway gives you a URL like:

```
https://driftcoach-backend-production.up.railway.app
```

**Verify**:

```bash
curl https://<your-railway-url>/api/demo
```

Should return `200 OK` with JSON.

---

## II. Frontend on Vercel 🎨

### 1️⃣ Frontend env vars

Create `frontend/.env`:

```bash
VITE_API_BASE=https://<your-railway-url>/api
```

⚠️ Replace `<your-railway-url>` with the Railway URL above.

### 2️⃣ Push to GitHub

```bash
git add .
git commit -m "Add Railway & Vercel deployment config"
git push
```

### 3️⃣ Deploy on Vercel

1. Visit https://vercel.com
2. Sign in with **GitHub**
3. Click **Import Project**
4. Choose the `DriftCoach-Backend-for-cloud9-hackthon-` repo
5. Configure:

**Root Directory**: `frontend`  
**Build Command**: `npm run build`  
**Output Directory**: `dist`

### 4️⃣ Add Vercel env vars

In Vercel project settings:
1. Go to **Settings** → **Environment Variables**
2. Add:

```bash
VITE_API_BASE=https://<your-railway-url>/api
```

3. Click **Redeploy**

---

## III. Acceptance ✅

Open the Vercel frontend URL (e.g., `https://driftcoach.vercel.app`) and ask:

1. **Give the review agenda for this match.**
2. **Where are the economic management issues?**
3. **Is this a high-risk matchup?**
4. **Summarize the key lessons.**

Requirements:
- ✅ Page stays up
- ✅ No safe mode
- ✅ Different answers per question

---

## IV. Deliverables 📦

You will get:

1. ✅ **Backend URL** (Railway): `https://<your-app>.up.railway.app`
2. ✅ **Frontend URL** (Vercel): `https://<your-app>.vercel.app`
3. ✅ **Demo status**: Confirmed working in browser

---

## 🔧 FAQs

### Railway rate-limited?

**Plan B** (slightly slower):
- [Render](https://render.com) — free but slower deploys
- [Fly.io](https://fly.io) — stable but needs credit card

### Vercel deploy failed?

Check:
1. `frontend/package.json` has `build` script
2. `VITE_API_BASE` is set correctly
3. Redeploy

### API CORS errors?

Ensure Railway variable:
```bash
CORS_ALLOW_ORIGINS=*
```

---

## 📝 Project files

We created:

- `Procfile` - Railway start command
- `.env.example` - Backend env template
- `frontend/.env.example` - Frontend env template
- `requirements.txt` - Python deps (updated)

---

## ⚡ Constraints

- ❌ No performance tuning
- ❌ No Docker/VPS
- ❌ No architecture refactor
- ✅ Only ensure demo is accessible and demo-ready

---

## 🎯 Next steps

1. **Deploy backend** → Railway
2. **Deploy frontend** → Vercel
3. **Test demo** → Browser verification
4. **Share links** → Send to owner

**Expected time**: 10–15 minutes

Good luck! 🚀
