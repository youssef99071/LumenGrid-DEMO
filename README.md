# LumenGrid

> **AI-powered road traffic detection — no cameras, no roadside sensors. Just the 5G network.**

LumenGrid is a proof-of-concept platform that detects road congestion by analyzing how physical vehicles disrupt 5G radio signals between cell towers. It uses Nokia Network as Code (NaC) / CAMARA cellular metrics (signal strength, match rate, neighbour count) to classify road occupancy in real time using a trained AI model.

---

## 🚦 The Concept

When cars fill a road, they physically block and scatter 5G signals between towers. LumenGrid reads this invisible disruption — analyzed over a 60-second window of signal data — and classifies traffic into five states:

`EMPTY` → `LOW_OCCUPANCY` → `NORMAL` → `SLOW` → `TRAFFIC_JAM`

**No cameras. No sensors. Just the network that already exists.**

---

## 🚀 Quick Start

### Requirements
- Python 3.9+
- Node.js 18+
- `python3-venv` (on Debian/Ubuntu: `sudo apt install python3-venv -y`)

### Run everything with one command

```bash
chmod +x run.sh
./run.sh
```

This script automatically:
1. Creates a Python virtual environment and installs all backend dependencies
2. Copies `.env.example` → `.env` if no `.env` exists
3. Generates the 5G tower map data (avoiding sea coordinates)
4. Installs frontend npm packages
5. Starts both the backend and frontend servers

| URL | Purpose |
|-----|---------|
| `http://localhost:5173` | **Dashboard UI (The Demo)** |
| `http://localhost:8000/docs` | API docs (Swagger) |

Press `Ctrl+C` to stop everything.

---

## 🎬 How to Run the Demo

The UI is built as a linear 3-step story to present to stakeholders:

### 1. The Data Tab
* **Action:** Click **"📥 Load Training Data"**.
* **What it does:** Feeds the AI 7 days of historical 5G signal data across 10 monitoring zones along Avenue Habib Bourguiba in Tunis. This teaches it what each traffic state looks like in radio waves.

### 2. The Learning Tab
* **Action:** Click **"🎓 Train the AI"**.
* **What it does:** Trains the Random Forest classifier on the data you just loaded in a matter of seconds.

### 3. The Simulation Tab (God Mode)
* **Action 1:** Under **Simulate a Traffic Scenario**, pick a traffic state (e.g. 🔴 Traffic jam), pick a location, and click **"📡 Generate 5G Signal Clip"**.
* **Action 2:** Under **Step 3 — Run Live Detection**, click **"▶ Run Live Detection"**.
* **What it does:** First, it generates the exact physical 5G radio disruption that scenario would cause. Second, it passes that raw radio data to the AI. The AI then correctly identifies the traffic state with high confidence, purely from the signal patterns.

*(Tip: You can reset the entire demo by simply going back to the Data tab and clicking "Load Training Data" again, or by deleting `backend/lumengrid.db` and restarting `./run.sh`).*

---

## 🛠 Tech Stack

| Layer | Stack |
|-------|-------|
| **Backend** | Python · FastAPI · SQLAlchemy · scikit-learn |
| **Frontend** | React 18 · TypeScript · Vite · Leaflet · Recharts |
| **ML Model** | Random Forest (60-second clip features: mean / std / wander / jitter / slope) |
| **Map Data** | Synthetic Ooredoo Tunisia (MCC 605 / MNC 03) tower grid |

---

## ⚙️ Notes & Configuration

- **Accuracy**: The PoC uses simulated synthetic data based on real-world physics principles. True real-world accuracy requires calibration per site, weather, and specific network topology configurations.
- **Tower data**: The map shows ~45k synthetic Ooredoo cell towers generated dynamically within a Tunisia land-boundary polygon. For production, replace `backend/data/ooredoo_towers.json` with a real OpenCelliD CSV export.
- **NaC credentials**: Add your Nokia NaC API keys to `backend/.env` to switch from sandbox mode to live production data.
