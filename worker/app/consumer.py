import pika
import json
import logging
import os
import redis
import time
from shared.config import Config
from shared.constants import QueueName, TaskStatus
from worker.app.processing import get_video_duration, split_video, transcode_chunk, merge_chunks

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoConsumer:
    def __init__(self):
        self.connection = None
        self.channel = None
        self.redis = redis.Redis(host=Config.REDIS_HOST, port=Config.REDIS_PORT, db=0, decode_responses=True)

    def connect(self):
        while True:
            try:
                credentials = pika.PlainCredentials(Config.RABBITMQ_USER, Config.RABBITMQ_PASS)
                parameters = pika.ConnectionParameters(
                    host=Config.RABBITMQ_HOST,
                    port=Config.RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )
                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()
                
                # Declare all queues
                self.channel.queue_declare(queue=QueueName.VIDEO_UPLOAD, durable=True)
                self.channel.queue_declare(queue=QueueName.VIDEO_CHUNK, durable=True)
                self.channel.queue_declare(queue=QueueName.VIDEO_MERGE, durable=True)
                
                # Set QoS
                self.channel.basic_qos(prefetch_count=1)
                
                logger.info("Connected to RabbitMQ")
                return
            except Exception as e:
                logger.error(f"Failed to connect to RabbitMQ, retrying in 5s: {e}")
                time.sleep(5)

    def start_consuming(self):
        if not self.connection or self.connection.is_closed:
            self.connect()
        
        # Register callbacks
        self.channel.basic_consume(queue=QueueName.VIDEO_UPLOAD, on_message_callback=self.handle_upload_task)
        self.channel.basic_consume(queue=QueueName.VIDEO_CHUNK, on_message_callback=self.handle_chunk_task)
        self.channel.basic_consume(queue=QueueName.VIDEO_MERGE, on_message_callback=self.handle_merge_task)
        
        logger.info("Waiting for messages...")
        self.channel.start_consuming()

    def handle_upload_task(self, ch, method, properties, body):
        task = json.loads(body)
        video_id = task['video_id']
        input_path = task['input_path']
        logger.info(f"Processing Upload Task for {video_id}")

        self.redis.set(f"video:{video_id}", "SPLITTING")

        try:
            # 1. Create directories
            # Use a specific directory for this video to avoid clutter and collisions
            base_dir = os.path.dirname(input_path) # /app/uploads
            video_dir = os.path.join(base_dir, video_id)
            chunks_dir = os.path.join(video_dir, "chunks")
            transcoded_dir = os.path.join(video_dir, "transcoded")
            
            # Create these directories
            os.makedirs(chunks_dir, exist_ok=True)
            os.makedirs(transcoded_dir, exist_ok=True)

            # 2. Split Video
            # Determine chunk size based on slice count
            slice_count = task.get('slice_count', 5)
            
            # Probe duration
            try:
                total_duration = get_video_duration(input_path)
            except Exception:
                logger.warning("Could not force probe duration, defaulting to 10s chunks")
                total_duration = slice_count * 10
            
            chunk_duration = max(1, total_duration / slice_count) # Ensure at least 1s
            logger.info(f"Splitting video {video_id} (Duration: {total_duration}s) into {slice_count} slices of {chunk_duration:.2f}s")

            chunks = split_video(input_path, chunk_duration, chunks_dir)
            
            total_chunks = len(chunks)
            self.redis.set(f"video:{video_id}:total_chunks", total_chunks)
            self.redis.set(f"video:{video_id}:processed_chunks", 0)

            # 3. Publish Chunk Tasks
            # Calculate threads allocation: 8 cores total / slice_count
            # e.g. 4 slices -> 2 threads each. 8 slices -> 1 thread each.
            threads_per_chunk = max(1, int(8 / slice_count))
            logger.info(f"Allocating {threads_per_chunk} threads per chunk for {slice_count} slices")

            for index, chunk_path in enumerate(chunks):
                chunk_task = {
                    "video_id": video_id,
                    "request_id": task.get("request_id", ""),
                    "chunk_path": chunk_path,
                    "chunk_index": index,
                    "total_chunks": total_chunks,
                    "target_format": task['target_format'],
                    "transcoded_dir": transcoded_dir,
                    "threads": threads_per_chunk
                }
                
                ch.basic_publish(
                    exchange='',
                    routing_key=QueueName.VIDEO_CHUNK,
                    body=json.dumps(chunk_task),
                    properties=pika.BasicProperties(delivery_mode=2)
                )

            logger.info(f"Split video {video_id} into {total_chunks} chunks")
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error handling upload task: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False) # Or True based on policy
            self.redis.set(f"video:{video_id}", TaskStatus.FAILED)

    def handle_chunk_task(self, ch, method, properties, body):
        task = json.loads(body)
        video_id = task['video_id']
        chunk_path = task['chunk_path']
        transcoded_dir = task['transcoded_dir']
        chunk_index = task['chunk_index']
        
        logger.info(f"Processing Chunk {chunk_index} for {video_id}")
        
        try:
            # 1. Transcode
            filename = os.path.basename(chunk_path)
            # Use same filename logic
            output_path = os.path.join(transcoded_dir, filename)
            
            threads = task.get('threads', 1)
            transcode_chunk(chunk_path, output_path, task['target_format'], threads=threads)
            
            # 2. Update Progress
            processed_count = self.redis.incr(f"video:{video_id}:processed_chunks")
            total_chunks = int(self.redis.get(f"video:{video_id}:total_chunks") or 1) # avoid div by zero
            
            progress = int((processed_count / total_chunks) * 100)
            self.redis.set(f"video:{video_id}:progress", progress)
            self.redis.set(f"video:{video_id}", f"PROCESSING {progress}%")

            # 3. Check for completion
            if processed_count >= total_chunks:
                logger.info(f"All chunks processed for {video_id}. Queueing merge.")
                merge_task = {
                    "video_id": video_id,
                    "transcoded_dir": transcoded_dir,
                    "target_format": task['target_format'],
                    "original_input_path": os.path.dirname(os.path.dirname(chunk_path)) # unused now
                }
                ch.basic_publish(
                    exchange='',
                    routing_key=QueueName.VIDEO_MERGE,
                    body=json.dumps(merge_task),
                    properties=pika.BasicProperties(delivery_mode=2)
                )

            ch.basic_ack(delivery_tag=method.delivery_tag)

        except Exception as e:
            logger.error(f"Error handling chunk task: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

    def handle_merge_task(self, ch, method, properties, body):
        task = json.loads(body)
        video_id = task['video_id']
        transcoded_dir = task['transcoded_dir']
        
        logger.info(f"Processing Merge Task for {video_id}")
        self.redis.set(f"video:{video_id}", "MERGING")

        try:
            logger.info(f"Scanning directory: {transcoded_dir}")
            # 1. Gather chunks
            # We rely on glob sorting to match index order if named correctly.
            chunks = []
            if os.path.exists(transcoded_dir):
                # Using scandir for efficiency
                with os.scandir(transcoded_dir) as entries:
                    chunks = sorted([e for e in entries if e.is_file()], key=lambda e: e.name)
            
            chunk_paths = [e.path for e in chunks]
            
            if not chunk_paths:
                logger.error(f"No chunks found in {transcoded_dir}")
                raise Exception("No chunks to merge")

            # 2. Merge
            # Output path: in the video_id folder
            output_dir = os.path.dirname(transcoded_dir) # video_dir
            output_path = os.path.join(output_dir, f"{video_id}_final.{task['target_format']}")
            
            merge_chunks(chunk_paths, output_path)
            
            # 3. Finalize
            self.redis.set(f"video:{video_id}", TaskStatus.COMPLETED)
            self.redis.set(f"video:{video_id}:progress", 100)
            logger.info(f"Video {video_id} completed: {output_path}")
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
            
        except Exception as e:
            logger.error(f"Error handling merge task: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            self.redis.set(f"video:{video_id}", TaskStatus.FAILED)

if __name__ == "__main__":
    consumer = VideoConsumer()
    consumer.connect()
    consumer.start_consuming()
