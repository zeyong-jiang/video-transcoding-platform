import requests
import time
import sys
import os
import websocket
import threading

API_URL = "http://localhost:8000/api/v1"
VIDEO_FILE = "test_video.mp4"

def test_upload_and_process():
    if not os.path.exists(VIDEO_FILE):
        print(f"Error: {VIDEO_FILE} not found. Run generate_video.sh first.")
        sys.exit(1)

    print(f"Uploading {VIDEO_FILE}...")
    with open(VIDEO_FILE, "rb") as f:
        files = {"file": f}
        data = {"target_format": "mp4"}
        response = requests.post(f"{API_URL}/upload", files=files, data=data)

    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        sys.exit(1)

    result = response.json()
    video_id = result["video_id"]
    print(f"Upload success! Video ID: {video_id}")
    
    # Connect to WebSocket to listen for updates
    ws_url = f"ws://localhost:8000/api/v1/ws/{video_id}"
    
    def on_message(ws, message):
        print(f"Status update: {message}")
        if "COMPLETED" in message:
            print("Processing Completed!")
            ws.close()
        elif "FAILED" in message:
            print("Processing Failed!")
            ws.close()

    def on_error(ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(ws, close_status_code, close_msg):
        print("WebSocket closed")

    ws = websocket.WebSocketApp(ws_url,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    
    # Run WS in separate thread or just blocking? 
    # Blocking is fine since we just want to wait for completion.
    print("Connecting to WebSocket...")
    ws.run_forever()

if __name__ == "__main__":
    # Wait via poll if needed, or just run
    try:
        test_upload_and_process()
    except KeyboardInterrupt:
        print("Aborted")
