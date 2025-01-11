import time
import logging
import signal
import sys
import threading
from contextlib import contextmanager
from typing import Optional, Dict, Any
from dotenv import dotenv_values

from server import XMLRPCServer
from client import HTTPClient


class Config:
    """Configuration handler for XMLRPC HomeMatic."""

    def __init__(self, env_file: str = ".env"):
        self.config: Dict[str, Any] = dotenv_values(env_file)
        self.validate()

    def validate(self) -> None:
        """Validate required configuration values."""
        required_keys = [
            "SERVER_IP",
            "SERVER_PORT",
            "HM_SERVER_IP",
            "HM_SERVER_HMIP_PORT",
            "HM_SERVER_VIRTUALDEVICES_PORT",
            "HM_USERNAME",
            "HM_PASSWORD",
            "HM_DEVICES",
        ]
        missing = [key for key in required_keys if key not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")


class XMLRPC_HOMEMATIC:
    """HomeMatic XML-RPC Server and Client Manager."""

    STARTUP_DELAY = 1  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self):
        self.config = Config().config
        self._setup_logging()
        self.server: Optional[XMLRPCServer] = None
        self.client_hmip: Optional[HTTPClient] = None
        self.client_virtual: Optional[HTTPClient] = None
        self._shutdown_event = threading.Event()

    def _setup_logging(self) -> None:
        """Configure logging for the application."""
        log_level = getattr(logging, self.config.get("LOG_LEVEL", "INFO").upper())
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.server_logger = logging.getLogger("server")
        self.client_logger = logging.getLogger("client")
        self.server_logger.setLevel(log_level)
        self.client_logger.setLevel(log_level)

    def setup(self) -> None:
        """Initialize server and clients."""
        self.server_logger.debug("Starting setup...")
        device_tuple = tuple(self.config.get("HM_DEVICES", "").strip().split(","))

        self._setup_server(device_tuple)
        self._setup_clients()

    def _setup_server(self, device_tuple) -> None:
        """Initialize XML-RPC server."""
        self.server = XMLRPCServer(
            host=self.config["SERVER_IP"],
            port=int(self.config["SERVER_PORT"]),
            logger=self.server_logger,
            ccu_device_ids=device_tuple,
            server_id="xmlrpc-server",
        )

    def _setup_clients(self) -> None:
        """Initialize HomeMatic clients."""
        base_url = f"http://{self.config['HM_SERVER_IP']}"
        self.client_hmip = self._create_client(
            f"{base_url}:{self.config['HM_SERVER_HMIP_PORT']}", "HmIP-RF"
        )
        self.client_virtual = self._create_client(
            f"{base_url}:{self.config['HM_SERVER_VIRTUALDEVICES_PORT']}/groups",
            "VirtualDevices",
        )

    def _create_client(self, server_url: str, interface: str) -> HTTPClient:
        """Create and configure HTTP client."""
        return HTTPClient(
            ccu=server_url,
            xmlRpcServer=f"{self.config['SERVER_IP']}:{self.config['SERVER_PORT']}",
            username=self.config["HM_USERNAME"],
            password=self.config["HM_PASSWORD"],
            register_id=interface,  # Interface (HmIP-RF/VirtualDevices) identifies CCU client type
            logger=self.client_logger,
        )


@contextmanager
def lifespan(app: XMLRPC_HOMEMATIC):
    """Manage application lifecycle."""
    try:
        logging.info("=============== Initializing application... ===============")
        app.setup()

        logging.debug("=============== Starting XML-RPC server... ===============")
        app.server.start()
        time.sleep(app.STARTUP_DELAY)

        logging.info("================== Registering clients... =================")
        app.client_hmip.register()
        app.client_virtual.register()
        logging.info("========== Setup complete, entering main loop... ==========")

        yield
    except Exception as e:
        logging.error(f"Error during startup: {e}", exc_info=True)
        raise
    finally:
        logging.info("================= Graceful shutdown... ==================")
        for client in [app.client_hmip, app.client_virtual]:
            if client:
                try:
                    client.unregister()
                except Exception as e:
                    logging.error(f"Error unregistering client: {e}")
        if app.server:
            app.server.stop()


def main():
    app = XMLRPC_HOMEMATIC()
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    with lifespan(app):
        try:
            while not app._shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            app._shutdown_event.set()


if __name__ == "__main__":
    main()
