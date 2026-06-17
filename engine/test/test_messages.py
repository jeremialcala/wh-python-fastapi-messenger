"""
    This class test controllers/messages.py
"""
from unittest.mock import patch, MagicMock


def test_process_messages():
    """
        This test the method process_messages from controllers
    """
    with patch("pika.BlockingConnection") as mock_connection:
        mock_channel = MagicMock()
        mock_channel.queue_bind()
        mock_connection.return_value.channel.return_value = mock_channel
