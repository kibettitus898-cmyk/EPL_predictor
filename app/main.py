from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import matches, predict, pipeline
from app.core.config import settings
import logging

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EPL Match Outcome Predictor",
    description="Predicts EPL match outcomes using Random Forest + engineered features",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-vercel-app.vercel.app",  # ← replace with real URL at deploy time
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers registered flat — endpoint decorators carry full sub-paths
app.include_router(matches.router,  prefix="/api/v1", tags=["Matches"])
app.include_router(predict.router,  prefix="/api/v1", tags=["Predictions"])
app.include_router(pipeline.router, prefix="/api/v1", tags=["Pipeline"])

@app.get("/health")
def health_check():
    return {"status": "ok", "version": "1.0.0"}