
title: EPL Predictor API
emoji: ⚽
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# EPL Match Outcome Predictor

A production-grade machine learning system that predicts English Premier League match outcomes and identifies value bets using ensemble modelling, ELO ratings, and live Bet365 odds.

---

## Table of Contents

- [Project Overview](#project-overview)
- [System Architecture](#system-architecture)
- [Machine Learning Pipeline](#machine-learning-pipeline)
- [Feature Engineering](#feature-engineering)
- [API Reference](#api-reference)
- [Value Bet & EV Analysis](#value-bet--ev-analysis)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Setup & Installation](#setup--installation)
- [Deployment](#deployment)
- [Results & Model Performance](#results--model-performance)
- [Roadmap](#roadmap)

---

## Project Overview

This system predicts the outcome of EPL matches (Home Win / Draw / Away Win) by combining:

- **Historical match data** from football-data.co.uk ingested into Supabase
- **Rolling form features** capturing recent team performance
- **ELO ratings** updated dynamically after each match
- **PI ratings** (Performance Index) derived from match statistics
- **Live Bet365 odds** via OddsPapi for real-time EV analysis

The system is designed as a **REST API** consumed by a Next.js frontend and is fully containerised for deployment on Hugging Face Spaces.

---

## System Architecture

```

┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                     │
│              (Vercel — epl-predictor.vercel.app)        │
└───────────────────────┬─────────────────────────────────┘
│ REST API calls
▼
┌─────────────────────────────────────────────────────────┐
│              FastAPI Backend (Docker)                   │
│         (Hugging Face Spaces — port 7860)               │
│                                                         │
│  POST /api/v1/predict          ← manual prediction      │
│  GET  /api/v1/predict/upcoming ← live gameweek          │
│  GET  /health                  ← status check           │
└────────┬──────────────────────────┬─────────────────────┘
│                          │
▼                          ▼
┌─────────────────┐      ┌─────────────────────────────┐
│    Supabase     │      │         OddsPapi             │
│  (PostgreSQL)   │      │  (Live Bet365 1X2 odds)      │
│  Match history  │      │  EPL upcoming fixtures       │
│  ELO ratings    │      └─────────────────────────────┘
│  Feature matrix │
└─────────────────┘

```

---

## Machine Learning Pipeline

### Model Architecture

The system uses a **stacking ensemble** of three base learners:

| Model | Role | Key Strength |
|---|---|---|
| Random Forest | Base learner 1 | Robust to outliers, feature importance |
| XGBoost | Base learner 2 | Gradient boosting, handles tabular data |
| LightGBM | Base learner 3 | Fast training, high accuracy on structured data |
| Logistic Regression | Meta-learner | Combines base learner probabilities |

### Training Process

1. **Data ingestion** — historical EPL seasons pulled from Supabase
2. **Feature engineering** — rolling stats, ELO, PI ratings computed per match
3. **Train/test split** — time-based split to prevent data leakage (no random shuffle)
4. **Imputation** — median imputer handles missing early-season rolling stats
5. **Training** — base learners trained independently, meta-learner trained on out-of-fold predictions
6. **Serialisation** — `ensemble.pkl`, `imputer.pkl`, `feature_names.pkl` saved via joblib

### Why Stacking?

A single model tends to overfit to particular patterns — Random Forest may over-weight home advantage while XGBoost may over-weight recent form. Stacking lets a meta-learner combine their strengths and produce better-calibrated probabilities, which is critical for accurate EV calculations.

---

## Feature Engineering

Features are grouped into four categories:

### Rolling Form Features (last 5 matches)
| Feature | Description |
|---|---|
| `h_form_gf` | Home team goals scored (rolling 5) |
| `h_form_ga` | Home team goals conceded (rolling 5) |
| `h_form_pts` | Home team points earned (rolling 5) |
| `a_form_gf` | Away team goals scored (rolling 5) |
| `a_form_ga` | Away team goals conceded (rolling 5) |
| `h_win_rate` | Home team win rate (rolling 5) |

### ELO Ratings
ELO ratings are updated after each match using a standard K-factor formula. Higher ELO = stronger team. The `elo_diff` (home ELO minus away ELO) is the single most predictive feature in the model.

| Feature | Description |
|---|---|
| `home_elo` | Home team current ELO |
| `away_elo` | Away team current ELO |
| `elo_diff` | Difference (home − away) |

### PI Ratings (Performance Index)
Derived from shots, corners, and possession data to measure dominance beyond goals.

| Feature | Description |
|---|---|
| `h_pi_hc` | Home corners performance index |
| `h_pi_hd` | Home shots on target performance index |
| `a_pi_ac` | Away corners performance index |

### Odds-Derived Features (optional)
When Bet365 odds are provided:

| Feature | Description |
|---|---|
| `odds_fair_h` | Fair home win probability (vig-removed) |
| `odds_fair_d` | Fair draw probability |
| `odds_fair_a` | Fair away win probability |
| `odds_home_edge` | Model edge over market on home team |

---

## API Reference

### `GET /health`
Returns API status.
```json
{"status": "ok", "version": "1.0.0"}
```


---

### `POST /api/v1/predict`

Predict outcome for any EPL fixture. Odds are optional — include them for EV analysis.

**Request:**

```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "home_odd": 2.10,
  "draw_odd": 3.40,
  "away_odd": 3.20
}
```

**Response:**

```json
{
  "home_team": "Arsenal",
  "away_team": "Chelsea",
  "probabilities": {"H": 0.467, "D": 0.295, "A": 0.238},
  "predicted": "H",
  "label": "Home Win",
  "confidence": 0.467,
  "ev_analysis": {
    "bookmaker_vig": 0.0828,
    "has_value": false,
    "best_bet": null,
    "value_bets": [],
    "all_outcomes": [
      {
        "outcome": "H",
        "model_prob": 0.467,
        "decimal_odd": 2.10,
        "ev": -0.019,
        "kelly_pct": 0.0,
        "is_value": false
      }
    ]
  }
}
```


---

### `GET /api/v1/predict/upcoming?limit=20`

Fetches all upcoming EPL fixtures from OddsPapi, runs predictions, and returns full EV analysis per fixture. No input required.

**Sample response item:**

```json
{
  "fixture_id": "id1000001761301189",
  "date": "2026-04-24T19:00:00.000Z",
  "home_team": "Fulham",
  "away_team": "Aston Villa",
  "b365": {"h": 2.75, "d": 3.60, "a": 2.45},
  "probabilities": {"H": 0.290, "D": 0.338, "A": 0.371},
  "predicted": "A",
  "label": "Away Win",
  "confidence": 0.371,
  "ev_analysis": {
    "bookmaker_vig": 0.0496,
    "has_value": true,
    "best_bet": {
      "outcome": "D",
      "model_prob": 0.338,
      "decimal_odd": 3.60,
      "ev": 0.2175,
      "kelly_pct": 8.37,
      "is_value": true
    },
    "value_bets": [...],
    "all_outcomes": [...]
  }
}
```


---

## Value Bet \& EV Analysis

### Expected Value (EV)

```
EV = (model_probability × decimal_odd) − 1
```

- `EV > 0.05` → value bet (model believes the bet is underpriced by the bookmaker)
- `EV < 0` → no value (bookmaker has the edge)


### Kelly Criterion

The Kelly % tells you how much of your bankroll to stake:

```
Kelly % = ((prob × odd − 1) / (odd − 1)) × 100
```

Kelly is capped at **15%** per bet to limit variance. A Kelly of 0% means no edge — do not bet.

### Bookmaker Vig

The vig (overround) measures how much the bookmaker charges:

```
Vig = (1/homeOdd + 1/drawOdd + 1/awayOdd) − 1
```

A vig of 0.05 means the bookmaker takes ~5% on every pound wagered. Lower vig = fairer odds.

---

## Tech Stack

| Layer | Technology |
| :-- | :-- |
| API Framework | FastAPI |
| ML Models | scikit-learn, XGBoost, LightGBM, CatBoost |
| Data Storage | Supabase (PostgreSQL) |
| Model Serialisation | joblib |
| Live Odds | OddsPapi (Bet365 1X2) |
| Containerisation | Docker |
| Backend Hosting | Hugging Face Spaces |
| Frontend | Next.js + TypeScript |
| Frontend Hosting | Vercel |
| Data Source | football-data.co.uk |


---

## Project Structure

```
epl_predictor_v2/
├── app/
│   ├── api/v1/endpoints/
│   │   ├── predict.py        ← prediction endpoints
│   │   ├── matches.py        ← historical match data
│   │   └── pipeline.py       ← model retraining trigger
│   ├── core/
│   │   ├── config.py         ← settings + env vars
│   │   └── supabase_client.py
│   ├── ml/
│   │   ├── features/
│   │   │   └── feature_columns.py
│   │   ├── models/
│   │   │   ├── random_forest_model.py
│   │   │   ├── xgb_model.py
│   │   │   └── lgbm_model.py
│   │   └── stacking.py       ← ensemble meta-learner
│   ├── schemas/
│   │   ├── prediction.py     ← request/response schemas
│   │   └── match.py
│   ├── services/
│   │   ├── feature_service.py  ← load + engineer features
│   │   ├── odds_service.py     ← OddsPapi integration
│   │   └── ev_service.py       ← EV + value bet logic
│   ├── utils/
│   │   └── team_utils.py     ← team name normalisation
│   └── main.py               ← FastAPI app + CORS
├── models/saved/
│   ├── ensemble.pkl
│   ├── imputer.pkl
│   ├── feature_names.pkl
│   └── elo_ratings.json
├── scripts/
│   ├── train_model.py        ← full training pipeline
│   ├── build_features.py     ← feature matrix builder
│   ├── ingest_seasons.py     ← historical data ingestion
│   └── predict_upcoming.py   ← CLI version of upcoming endpoint
├── tests/
│   └── unit/
├── Dockerfile
├── requirements.txt
└── README.md
```


---

## Setup \& Installation

### Prerequisites

- Python 3.11+
- Supabase project with match data
- OddsPapi API key


### Local setup

```bash
git clone https://github.com/YOUR_USERNAME/epl-predictor-v2
cd epl-predictor-v2

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_KEY, ODDSPAPI_KEY
```


### Train the model

```bash
python scripts/ingest_seasons.py   # pull historical data into Supabase
python scripts/build_features.py   # engineer feature matrix
python scripts/train_model.py      # train ensemble + save .pkl files
```


### Run locally

```bash
uvicorn app.main:app --reload --port 8000
# API available at http://localhost:8000
# Swagger docs at http://localhost:8000/docs
```


---

## Deployment

### Backend — Hugging Face Spaces (Docker)

1. Push repo to your HF Space git remote
2. Add secrets: `SUPABASE_URL`, `SUPABASE_KEY`, `ODDSPAPI_KEY`
3. HF builds the Docker image and starts uvicorn on port 7860
4. API live at `https://YOUR_USERNAME-epl-predictor-api.hf.space`

### Frontend — Vercel

1. Connect GitHub repo in Vercel dashboard
2. Set env var: `NEXT_PUBLIC_API_URL=https://YOUR_USERNAME-epl-predictor-api.hf.space`
3. Deploy — Vercel handles everything else

---

## Results \& Model Performance

| Metric | Value |
| :-- | :-- |
| Model type | Stacking Ensemble (RF + XGB + LGBM) |
| Train/test split | Time-based (no leakage) |
| Top feature | `elo_diff` |
| Fixtures covered (live) | 15–17 per EPL gameweek |
| EV threshold for value bets | > 5% |
| Kelly cap | 15% of bankroll |


---

## Roadmap

- [ ] Add player availability / injury data as features
- [ ] Add xG (expected goals) as a rolling feature
- [ ] Add Telegram/email alerts for high-EV value bets
- [ ] Retrain model automatically each week via pipeline endpoint
- [ ] Add historical backtest results per season

---

## Environment Variables

| Variable | Description |
| :-- | :-- |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `ODDSPAPI_KEY` | OddsPapi API key for live odds |
| `LOG_LEVEL` | Logging level (default: `INFO`) |
| `MODELS_DIR` | Path to saved models (default: `models/saved`) |
| `FEATURES_PARQUET` | Path to cached feature matrix |

## Frontend — Next.js

### Stack

- **Next.js 15** with App Router and TypeScript
- **Tailwind CSS v4** (CSS-first configuration, no `tailwind.config.ts`)
- **shadcn/ui** component library (Card, Badge, Button, Input, Label, Skeleton)
- **Vercel** for deployment

### Pages

| Route | Type | Purpose |
|---|---|---|
| `/upcoming` | Server Component + Suspense | Fetches all upcoming fixtures with predictions and EV |
| `/predict` | Client Component | Manual prediction form with odds input and validation |
| `/results` | Server Component + Suspense | Historical match results with model accuracy stats |

### Component Architecture

```
src/
├── app/
│   ├── upcoming/page.tsx    ← GET /predict/upcoming → UpcomingCard grid
│   ├── predict/page.tsx     ← POST /predict → PredictionResult
│   └── results/page.tsx     ← GET /matches → MatchCard grid + AccuracyStats
├── components/match/
│   ├── MatchCard.tsx        ← shared card for both results and predict output
│   ├── PredictionBadge.tsx  ← H/D/A probability bar
│   ├── OddsRow.tsx          ← B365 odds display
│   └── EVTable.tsx          ← per-outcome EV/Kelly table
├── components/stats/
│   └── AccuracyStats.tsx    ← model accuracy summary
├── lib/
│   ├── api.ts               ← typed API client (all fetch calls)
│   └── errors.ts            ← HTTP status → user-friendly message map
└── types/
    └── index.ts             ← all TypeScript interfaces
```

### Key UI Rules

**Confidence colouring** signals prediction strength at a glance:
- ≥ 50% confidence → green bold
- 40–50% → amber bold
- < 40% → muted grey

**EV colouring** per outcome row:
- `EV > 5%` → green highlight (value bet)
- `EV > 0%` → neutral
- `EV < 0%` → muted red

**Value bets float to the top** of the upcoming fixtures grid, ensuring the most actionable predictions are immediately visible.

**Odds validation** on the predict form enforces an all-or-nothing rule — if any odd is entered, all three must be provided and each must be between 1.01 and 100. This prevents partial EV computations that would produce misleading results.

### Rendering Strategy

Pages that fetch live backend data use `export const dynamic = "force-dynamic"` to opt out of Next.js static pre-rendering at build time. This is necessary because Vercel's build servers cannot reach the FastAPI backend during `next build`. The pages render fresh on every request at runtime instead.

---