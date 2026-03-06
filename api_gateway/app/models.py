from pydantic import BaseModel

class VideoUploadRequest(BaseModel):
    filename: str
    target_format: str = "mp4"

class VideoTask(BaseModel):
    video_id: str
    input_path: str
    output_path: str
    target_format: str
    status: str
