# Deploy on Render – Single Service (Recommended)

This is the **easiest** way to host the full Binance-style paper trading UI.

Paper trading runs inside the same process using local SQLite.
No second service needed.

---

## 1. Push to GitHub

```bash
cd tradingview_realtime_python
git init
git add .
git commit -m "Ready for Render single service"
# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## 2. Create one Web Service on Render

1. Go to https://dashboard.render.com → **New → Web Service**
2. Connect your GitHub repository
3. Fill in these settings:

| Setting            | Value                                      |
|--------------------|--------------------------------------------|
| **Name**           | binance-trading-ui (or any name)           |
| **Root Directory** | `web_app`                                  |
| **Runtime**        | Python 3                                   |
| **Build Command**  | `pip install -r requirements.txt`          |
| **Start Command**  | `python binance_app.py`                    |
| **Instance Type**  | Free                                       |

4. (Optional) Environment variables:

| Key            | Value   | Notes                          |
|----------------|---------|--------------------------------|
| TRADING_MODE   | paper   | Default is already paper       |

5. Click **Create Web Service**

---

## 3. Open your app

After the build finishes (1–3 minutes) you will get a public URL:

`https://binance-trading-ui-xxxx.onrender.com`

The header badge should show **PAPER**.

---

## Notes

- Free tier services sleep after ~15 minutes of inactivity.  
  First request after sleep can take 30–50 seconds.
- The SQLite paper-trading database is **ephemeral** (it resets every time the service restarts or redeploys). This is normal on the free tier.
- Local development still works exactly the same:

```bash
cd web_app
pip install -r requirements.txt
python binance_app.py
```

Then open http://127.0.0.1:8050
