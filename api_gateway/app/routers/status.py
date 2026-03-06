from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import redis.asyncio as redis
from shared.config import Config

router = APIRouter()

# Simple in-memory connection manager for demo purposes
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()
redis_client = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=0, decode_responses=True)

@router.websocket("/ws/{video_id}")
async def websocket_endpoint(websocket: WebSocket, video_id: str):
    await manager.connect(websocket)
    try:
        while True:
            # simple echo/status check loop for now
            # In a real scenario, we might subscribe to a Redis channel or poll Redis
            status = await redis_client.get(f"video:{video_id}")
            if status:
                await websocket.send_text(status)
            else:
                 await websocket.send_text("Checking status...")
            await asyncio.sleep(1)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
import asyncio
