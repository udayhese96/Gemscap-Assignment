# Gemscap – Real‑time Statistical Arbitrage Dashboard

---

## 🎯 Project Overview

**Gemscap** is a premium‑grade Streamlit dashboard that streams live Binance Futures trade data, computes a suite of quantitative analytics, and visualises them with glass‑morphism styling.  The goal is to showcase **statistical validation, regime detection, and signal efficacy** for a statistical‑arbitrage strategy – exactly the kind of work a quant developer interview expects.

---

## 🏗️ Architecture Diagram

```mermaid
flowchart TD
    A[Binance Futures WebSocket] -->|Live trades| B[SyncWebSocketClient]
    B --> C[GlobalState (thread‑safe singleton)]
    C --> D[Analytics Engine]
    D --> E[Plotly Charts]
    E --> F[Streamlit UI]
    style A fill:#0ea5e9,stroke:#1e293b,color:#e2e8f0
    style B fill:#8b5cf6,stroke:#1e293b,color:#e2e8f0
    style C fill:#22c55e,stroke:#1e293b,color:#e2e8f0
    style D fill:#f59e0b,stroke:#1e293b,color:#e2e8f0
    style E fill:#ef4444,stroke:#1e293b,color:#e2e8f0
    style F fill:#0f172a,stroke:#1e293b,color:#e2e8f0
```

---

## 📊 Charts & Insights

| Chart | What it Shows | Key Insight |
|-------|--------------|-------------|
| **Z‑Score Distribution (Histogram)** | Frequency of Z‑scores, highlighting tails beyond ±2 | Validates that the ±2 threshold captures extreme events and quantifies tail risk |
| **Rolling Volatility of Spread** | Rolling standard deviation of the spread | Detects regime shifts – low volatility + high |Z| is a high‑probability entry zone; high volatility suggests staying out |
| **Rolling Hedge Ratio (β)** | Time‑varying β from rolling regression of the two assets | Stable β → model still valid; drifting β signals structural change and need for re‑calibration |
| **Signal‑Efficacy (Z vs Future Δ)** | Scatter of current Z‑score vs future spread change (look‑ahead 5 bars) with trend line | Negative slope = strong mean‑reversion → good predictive power of the Z‑score signal |
| **Z‑Score with Entry/Exit Markers** | Z‑score line with triangle markers for BUY/SELL entries (|Z| > 2) and circle markers for exits (crosses 0) | Gives a clear, visual trading logic – exactly what a trader would act on |

---

## 🖼️ Dashboard Snapshots

<div style="display:flex; justify-content:space-around; gap:10px;">
  <img src="file:///d:/Coding%20Area/Gemscap/image_1.png" alt="Dashboard Overview" width="30%"/>
  <img src="file:///d:/Coding%20Area/Gemscap/image_2.png" alt="Advanced Analytics" width="30%"/>
  <img src="file:///d:/Coding%20Area/Gemscap/image_3.png" alt="Z‑Score Signals" width="30%"/>
</div>

---

## 🚀 How to Run

```bash
# Clone the repo (if you haven't already)
git clone <repo-url>
cd Gemscap

# Install dependencies
pip install -r requirements.txt

# Start the dashboard
streamlit run app.py
```

The dashboard will automatically connect to Binance, start ingesting live data, and refresh every second (configurable via `config.py`).

---

## 📁 Project Structure

```
Gemscap/
├─ app.py                # Streamlit UI & chart orchestration
├─ config.py             # Constants, colours, WS params
├─ src/
│   └─ ingestion/
│       ├─ websocket_client.py   # Async Binance WS client + Sync wrapper
│       └─ data_normalizer.py    # Normalises raw tick messages
├─ requirements.txt      # Python deps (including websockets>=12.0)
└─ README.md             # ★ This file ★
```

---

## 🎉 What the Interviewer Will See

* **Clean, modern UI** – glass‑morphism, dark theme, responsive layout.
* **Robust real‑time pipeline** – async WebSocket with reconnection, thread‑safe state.
* **Deep quantitative analytics** – five advanced charts each with a clear business insight.
* **Professional documentation** – concise overview, architecture diagram, chart table, and a three‑image gallery.

Feel free to tweak the `REFRESH_RATE_MS` in `config.py` or add more symbols/time‑frames to showcase extensibility.

---

*Happy hacking!*
