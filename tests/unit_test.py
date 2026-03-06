import unittest
from unittest.mock import MagicMock, patch, ANY
import json
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from worker.app.consumer import VideoConsumer
from shared.constants import QueueName

class TestVideoConsumer(unittest.TestCase):
    def setUp(self):
        self.consumer = VideoConsumer()
        self.consumer.connection = MagicMock()
        self.consumer.channel = MagicMock()
        self.consumer.redis = MagicMock()
        
        # Mock Redis get/incr/set
        self.consumer.redis.get.return_value = "5" # total chunks
        self.consumer.redis.incr.return_value = 1 # processed chunks

    @patch("worker.app.consumer.split_video")
    @patch("os.makedirs")
    def test_handle_upload_task(self, mock_makedirs, mock_split):
        # Setup
        mock_split.return_value = ["chunk1.mp4", "chunk2.mp4"]
        
        ch = MagicMock()
        method = MagicMock()
        body = json.dumps({
            "video_id": "test_video",
            "input_path": "/app/uploads/test.mp4",
            "target_format": "mp4"
        })

        # Execute
        self.consumer.handle_upload_task(ch, method, None, body)

        # Verify
        # 1. Directories created?
        self.assertTrue(mock_makedirs.called)
        
        # 2. Redis set?
        self.consumer.redis.set.assert_any_call("video:test_video", "SPLITTING")
        self.consumer.redis.set.assert_any_call("video:test_video:total_chunks", 2)
        
        # 3. Chunks published?
        self.assertEqual(ch.basic_publish.call_count, 2)
        # Verify first chunk call
        first_call = ch.basic_publish.call_args_list[0]
        # (args, kwargs) -> kwargs['body']
        body_sent = json.loads(first_call[1]['body'])
        self.assertEqual(body_sent['video_id'], "test_video")
        self.assertEqual(body_sent['chunk_index'], 0)
        self.assertEqual(body_sent['total_chunks'], 2)
        
        # 4. Ack?
        ch.basic_ack.assert_called_with(delivery_tag=method.delivery_tag)

    @patch("worker.app.consumer.transcode_chunk")
    def test_handle_chunk_task(self, mock_transcode):
        # Setup
        ch = MagicMock()
        method = MagicMock()
        body = json.dumps({
            "video_id": "test_video",
            "chunk_path": "/app/uploads/test/chunks/chunk2.mp4",
            "chunk_index": 1,
            "total_chunks": 5,
            "target_format": "mp4",
            "transcoded_dir": "/app/uploads/test/transcoded"
        })
        
        # Configure redis to simulate last chunk
        self.consumer.redis.incr.return_value = 5 # This is the 5th chunk
        self.consumer.redis.get.return_value = "5"

        # Execute
        self.consumer.handle_chunk_task(ch, method, None, body)

        # Verify
        # 1. Transcode called?
        mock_transcode.assert_called()
        
        # 2. Merge task published (since it's the last chunk)?
        ch.basic_publish.assert_called()
        args, kwargs = ch.basic_publish.call_args
        self.assertEqual(kwargs['routing_key'], QueueName.VIDEO_MERGE)
        
        # 3. Ack?
        ch.basic_ack.assert_called()

if __name__ == '__main__':
    unittest.main()
