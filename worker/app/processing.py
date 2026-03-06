import ffmpeg
import os
import logging
import subprocess
import glob

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_video_duration(input_path):
    try:
        probe = ffmpeg.probe(input_path)
        video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
        return float(video_stream['duration'])
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        raise

def split_video(input_path, chunk_duration, output_dir):
    """
    Splits video into chunks of `chunk_duration` seconds.
    Returns a list of chunk file paths.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Use segment muxer for more accurate splitting
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    segment_pattern = os.path.join(output_dir, f"{name}_%03d{ext}")
    
    try:
        (
            ffmpeg.input(input_path)
            .output(segment_pattern, c='copy', map=0, f='segment', segment_time=chunk_duration, reset_timestamps=1)
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg split error: {e.stderr.decode('utf8')}")
        raise

    # Return list of created chunks
    chunks = sorted(glob.glob(os.path.join(output_dir, f"{name}_*")))
    return chunks

def transcode_chunk(input_path, output_path, target_format, threads=1):
    try:
        # Simple transcoding example: just copy or re-encode. 
        # For this task, let's assume we re-encode to h264 if target is mp4
        # or just copy if same. To make it "transcode", let's force a preset.
        
        stream = ffmpeg.input(input_path)
        # Limit threads to specified count to allow parallel workers to coexist without CPU thrashing
        # Use ultrafast preset for maximum speed as requested
        stream = ffmpeg.output(stream, output_path, vcodec='libx264', preset='ultrafast', acodec='aac', threads=threads)
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        return output_path
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg transcode error: {e.stderr.decode('utf8')}")
        raise

def merge_chunks(chunk_paths, output_path):
    # Create a list file for concatenation
    list_file_path = f"{output_path}.txt"
    with open(list_file_path, 'w') as f:
        for chunk in chunk_paths:
            f.write(f"file '{chunk}'\n")

    try:
        (
            ffmpeg.input(list_file_path, format='concat', safe=0)
            .output(output_path, c='copy')
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg merge error: {e.stderr.decode('utf8')}")
        raise
    finally:
        if os.path.exists(list_file_path):
            os.remove(list_file_path)

    return output_path
