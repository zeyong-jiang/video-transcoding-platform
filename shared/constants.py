from enum import Enum

class QueueName(str, Enum):
    VIDEO_UPLOAD = "video_upload_queue"
    VIDEO_CHUNK = "video_chunk_queue"
    VIDEO_MERGE = "video_merge_queue"

class TaskStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
