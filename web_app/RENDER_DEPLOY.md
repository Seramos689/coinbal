# Deploy on Render (Two-Service Setup)

This project is ready for Render with a separate Backend (FastAPI) + Frontend (Dash).

## 1. Push to GitHub

```bash
git init
git add .
git commit -m "Ready for Render"
# Create repo on GitHub then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## 2. Create Backend Service

1. Go to https://dashboard.render.com → **New → Web Service**
2. Connect your GitHub repo
3. Settings:

| Setting          | Value |
|------------------|-------|
| Name             | paper-trading-api |
| Root Directory   | web_app |
| Runtime          | Python 3 |
| Build Command    | pip install -r requirements.txt |
| Start Command    | uvicorn backend.main:app --host 0.0.0.0 --port $PORT |
| Instance Type    | Free |

4. After deploy, copy the public URL (e.g. `https://paper-trading-api-xxxx.onrender.com`)

## 3. Create Frontend Service

1. **New → Web Service** again (same repo)
2. Settings:

| Setting          | Value |
|------------------|-------|
| Name             | binance-trading-ui |
| Root Directory   | web_app |
| Runtime          | Python 3 |
| Build Command    | pip install -r requirements.txt |
| Start Command    | python binance_app.py |
| Instance Type    | Free |

3. Go to **Environment** tab and add these variables:

| Key            | Value |
|----------------|-------|
| PAPER_API_URL  | https://paper-trading-api-xxxx.onrender.com |
| TRADING_MODE   | paper |

4. Deploy.

## 4. Open the Frontend URL

You will get a link like `https://binance-trading-ui-xxxx.onrender.com`

The header badge should show **PAPER (remote)**.

## Notes

- Free services sleep after ~15 minutes of inactivity.
- SQLite database on the backend is ephemeral (resets on every redeploy/restart).
- Local development still works the same (`python binance_app.py`).
