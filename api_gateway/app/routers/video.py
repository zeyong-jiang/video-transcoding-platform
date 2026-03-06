from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import uuid
import os
import shutil
from shared.config import Config
from shared.constants import TaskStatus
from api_gateway.app.models import VideoUploadRequest
from api_gateway.app.producer import producer
import redis

router = APIRouter()
redis_client = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=0, decode_responses=True)

@router.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    target_format: str = Form("mp4"),
    slice_count: int = Form(5)
):
    if not (3 <= slice_count <= 8):
        raise HTTPException(status_code=400, detail="Slice count must be between 3 and 8")

    video_id = str(uuid.uuid4())
    filename = f"{video_id}_{file.filename}"
    file_path = os.path.join(Config.SHARED_STORAGE_PATH, filename)

    # 1. Simulate Upload to Cloud Storage (Save to shared volume)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")

    # 2. Create Task Record in Redis
    redis_client.set(f"video:{video_id}", TaskStatus.PENDING)
    redis_client.set(f"video:{video_id}:progress", 0)

    # 3. Publish to RabbitMQ
    task_payload = {
        "video_id": video_id,
        "input_path": file_path,
        "filename": filename,
        "target_format": target_format,
        "slice_count": slice_count,
        "task_type": "new_video"
    }
    
    try:
        producer.publish_task(task_payload)
    except Exception as e:
         # Rollback?
         raise HTTPException(status_code=500, detail=f"Failed to queue task: {e}")

    # 4. Return "Pre-signed URL" (simulated) and Video ID
    return {
        "video_id": video_id,
        "message": "Video uploaded and processing started.",
        "simulated_url": file_path,
        "status_endpoint": f"/ws/{video_id}"
    }
