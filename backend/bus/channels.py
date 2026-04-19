"""Channel name builders for the Pusher bus.

Single dispatcher for the hackathon — everyone subscribes to `dispatcher.demo`.
"""


def dispatcher_channel(dispatcher_id: str = "demo") -> str:
    return f"dispatcher.{dispatcher_id}"


__all__ = ["dispatcher_channel"]
