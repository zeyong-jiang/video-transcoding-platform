#!/bin/bash
# Generate a 30-second video with a counter and noise
ffmpeg -f lavfi -i testsrc=duration=30:size=1280x720:rate=30 -f lavfi -i sine=frequency=1000:duration=30 -c:v libx264 -c:a aac -shortest test_video.mp4
