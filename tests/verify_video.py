import requests
import sys
import os
import websocket
import json
import time

API_URL = "http://localhost:8000/api/v1"

def verify_video(video_path):
    if not os.path.exists(video_path):
        print(f"Error: File {video_path} not found.")
        sys.exit(1)

    print(f"Uploading {video_path}...")
    try:
        with open(video_path, "rb") as f:
            files = {"file": f}
            data = {"target_format": "mp4"}
            response = requests.post(f"{API_URL}/upload", files=files, data=data)

        if response.status_code != 200:
            print(f"Upload failed: {response.text}")
            sys.exit(1)

        result = response.json()
        video_id = result["video_id"]
        print(f"Upload success! Video ID: {video_id}")
        print(f"Tracking progress via WebSocket...")
        
        ws_url = f"ws://localhost:8000/api/v1/ws/{video_id}"
        
        def on_message(ws, message):
            print(f"Status update: {message}")
            if "COMPLETED" in message:
                print("Processing Completed Successfully!")
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
        
        ws.run_forever()
        
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 verify_video.py <path_to_video>")
        sys.exit(1)
    
    verify_video(sys.argv[1])
