# EPL Match Outcome Predictor

A production-ready FastAPI backend that ingests historical EPL data from football-data.co.uk,
stores it in Supabase, engineers features, and serves predictions via a Random Forest model.

## Quick Start
```bash
cp .env.example .env          # fill in your credentials
pip install -r requirements.txt
python scripts/ingest_seasons.py   # loads all CSV seasons into Supabase
python scripts/train_model.py      # trains and saves the model
uvicorn app.main:app --reload      # start the API
```

## Seasons Available
1011, 1112, 1213, 1314, 1415, 1516, 1617, 1718, 1819, 1920, 2021, 2122, 2223, 2324, 2425
