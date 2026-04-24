# app/api/v1/endpoints/pipeline.py

import logging
import subprocess
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks
from app.services.ingest_service import ingest_all
from app.services.feature_service import build_and_save

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/pipeline/ingest")
def trigger_ingest(background_tasks: BackgroundTasks):
    background_tasks.add_task(ingest_all)
    return {"message": "Ingestion started in background"}

@router.post("/pipeline/train")
def trigger_train(background_tasks: BackgroundTasks):
    def run():
        try:
            # Step 1 — rebuild full feature parquet
            df = build_and_save()
            logger.info(f"✅ Features rebuilt: {df.shape}")

            # Step 2 — retrain the model using your main train script
            logger.info("🚀 Starting model training...")
            result = subprocess.run(
                ["python", "scripts/train_model.py"],
                capture_output=True,
                text=True,
                cwd="/home/scop/Betting AI/season specicific/EPL/epl_predictor"
            )
            if result.returncode == 0:
                logger.info(f"✅ Model training complete:\n{result.stdout[-500:]}")
            else:
                logger.error(f"❌ Training failed:\n{result.stderr[-500:]}")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)

    background_tasks.add_task(run)
    return {"message": "Pipeline started — rebuilding features then training model"}