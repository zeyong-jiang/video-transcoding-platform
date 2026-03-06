from fastapi import FastAPI
from api_gateway.app.routers import video, status
from api_gateway.app.producer import producer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Video Transcoding Platform API")

# Enable CORS for frontend
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, specify the frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    # Retry connection logic for RabbitMQ
    import time
    max_retries = 5
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            producer.connect()
            logger.info("Successfully connected to RabbitMQ")
            break
        except Exception as e:
            logger.warning(f"RabbitMQ connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("Could not connect to RabbitMQ after multiple attempts.")
                # We don't raise here to allow the app to start, but producer will fail on requests


@app.on_event("shutdown")
async def shutdown_event():
    producer.close()

app.include_router(video.router, prefix="/api/v1", tags=["videos"])
app.include_router(status.router, prefix="/api/v1", tags=["status"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Video Transcoding Platform API"}
