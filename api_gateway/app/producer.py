import pika
import json
import logging
from shared.config import Config
from shared.constants import QueueName

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TaskProducer:
    def __init__(self):
        self.connection = None
        self.channel = None

    def connect(self):
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
            # Declare the queue to ensure it exists
            self.channel.queue_declare(queue=QueueName.VIDEO_UPLOAD, durable=True)
            logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise e

    def publish_task(self, task: dict):
        if not self.channel or self.channel.is_closed:
            self.connect()
        
        try:
            self.channel.basic_publish(
                exchange='',
                routing_key=QueueName.VIDEO_UPLOAD,
                body=json.dumps(task),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                )
            )
            logger.info(f"Task published: {task}")
        except Exception as e:
            logger.error(f"Failed to publish task: {e}")
            raise e

    def close(self):
        if self.connection and not self.connection.is_closed:
            self.connection.close()

producer = TaskProducer()
