from worker.app.consumer import VideoConsumer
import logging

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    consumer = VideoConsumer()
    consumer.start_consuming()
