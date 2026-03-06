import os

class Config:
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", 5672))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASS = os.getenv("RABBITMQ_PASS", "guest")
    
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    
    # Path to simulated cloud storage
    SHARED_STORAGE_PATH = os.getenv("SHARED_STORAGE_PATH", "./uploads")
