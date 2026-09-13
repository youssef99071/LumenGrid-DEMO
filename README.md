# LumenGrid

Proof-of-concept: **5G signal scatter → road occupancy**, using Nokia NaC / CAMARA + cell radio metrics, labeled like Google Maps traffic, with a trained classifier.

## Idea rating (feasibility)

| Step | Verdict |
|------|---------|
| 1. Learning (anchor features + Maps/user labels) | **Feasible** for PoC — CAMARA `match_rate` + RSRP/RSRQ as density proxies is a credible sensing story; real Maps APIs can replace synthetic labels later |
| 2. Train AI model | **Feasible** — supervised RF/GBM on those features; PoC uses RandomForest (~99% on synthetic separable bands) |
| 3. Sample request (partial modalities) | **Feasible** — impute missing GPS or cellinfo; expect lower confidence when sensors are missing |
| 4. Per-anchor map occupancy | **Feasible** — batch predict latest sample per anchor |

**Caveat:** Real-world accuracy needs calibration per site, weather, and network config. The PoC proves the *pipeline*; production would use live NaC + Maps Ground Truth.

## Occupancy classes

`EMPTY` → `LOW_OCCUPANCY` → `NORMAL` → `SLOW` → `TRAFFIC_JAM`

## Tunis tower layer (OpenCelliD)

The map loads **real OpenCelliD** Ooredoo cells for Greater Tunis (MCC 605 / MNC 03) via tiled `getInArea` (full history, not the 18-month country dump). The API allows ~1000 calls/day and boxes of at most 4 km²; the script resumes if you run it again after the daily reset.

```bash
cd backend
# OPENCELLID_API_KEY in .env
PYTHONPATH=.vendor python3 scripts/download_ooredoo_towers.py
# → data/ooredoo_towers.csv
curl -X POST http://localhost:8000/api/towers/reload
```

Toggle **Show Ooredoo towers** on the map. Data © [OpenCelliD](https://opencellid.org/) (CC BY-SA 4.0).

Both training and inference operate on **60s sequences** (1 Hz), not single snapshots:

- Per-channel features: mean / std / min / max / **wander** (range) / **jitter** (std of Δ) / slope  
- GPS wander/jitter when modality includes location  
- Simulation records a clip live, then runs **one clip-level match** at the end  

```bash
# Synthesize + match a 60s TRAFFIC_JAM clip
curl -X POST http://localhost:8000/api/ml/predict \
  -H 'Content-Type: application/json' \
  -d '{"modality":"full","scenario":"TRAFFIC_JAM"}'
```

## Quick start

```bash
# Backend
cd backend
PYTHONPATH=.vendor ./run.sh   # or venv + uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

UI: http://localhost:5173 · API docs: http://localhost:8000/docs

## Key APIs

| Endpoint | Role |
|----------|------|
| `POST /api/dataset/seed-demo` | Learning-phase data (7 days) |
| `POST /api/ml/train` | Train RandomForest |
| `POST /api/ml/predict` | One-shot sample (choose modality) |
| `POST /api/ml/predict-anchors` | Occupancy for every map anchor |
| `POST /api/simulation/run` | 60s What-If stream over `/ws` |
| `GET /api/nac/*` | Nokia NaC / CAMARA sandbox |
