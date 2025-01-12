import socket
import os
from typing import Optional


def sd_notify(message: str) -> bool:
    """Send notification to systemd."""
    sock: Optional[socket.socket] = None
    try:
        notify_socket = os.environ.get("NOTIFY_SOCKET")
        if not notify_socket:
            return False

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        # Handle abstract namespace socket
        if notify_socket.startswith("@"):
            notify_socket = "\0" + notify_socket[1:]

        sock.connect(notify_socket)
        sock.sendall(message.encode())
        return True
    except Exception as e:
        print(f"Failed to notify systemd: {e}")
        return False
    finally:
        if sock:
            sock.close()


def watchdog():
    """Send watchdog notification."""
    return sd_notify("WATCHDOG=1")


def ready():
    """Notify service is ready."""
    return sd_notify("READY=1")


def status(status_line: str):
    """Update service status."""
    return sd_notify(f"STATUS={status_line}")


def stopping():
    """Notify service is stopping."""
    return sd_notify("STOPPING=1")
