import time
import logging
import signal
import sys
import threading
from contextlib import contextmanager
from typing import Optional, Tuple, Dict, Any
from dotenv import dotenv_values

from server import XMLRPCServer
from client import HTTPClient
from notify import ready, stopping, watchdog, status


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
            "ALLOWED_CLIENTS",
            "HM_SERVER_IP",
            "HM_USERNAME",
            "HM_PASSWORD",
            "HM_DEVICES",
            "DB_FILE",
            "SUBSCRIBE_TO",
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
        self.logger = self._setup_logging()
        self.server: Optional[XMLRPCServer] = None
        self.client: Optional[HTTPClient] = None
        self.client_bidcos: Optional[Dict[str, Any]] = None
        self.CCU_TYPES = {
            "BidCos-RF": {
                "register_id": "BidCos-RF",
                "url": f"http://{self.config['HM_SERVER_IP']}:2001",
            },
            "HmIP-RF": {
                "register_id": "HmIP-RF",
                "url": f"http://{self.config['HM_SERVER_IP']}:2010",
            },
            "VirtualDevices": {
                "register_id": "VirtualDevices",
                "url": f"http://{self.config['HM_SERVER_IP']}:9292/groups",
            },
        }
        self._shutdown_event = threading.Event()

    def _convert_to_tuple(self, key: str) -> Optional[Tuple[str, ...]]:
        """Convert comma-separated string to tuple, handling edge cases."""
        value = self.config.get(key, "").strip()
        if not value:
            return None

        items = [item.strip() for item in value.split(",") if item.strip()]
        return tuple(items) if items else None

    def _setup_logging(self) -> None:
        """Configure logging for the application."""
        log_level = getattr(logging, self.config.get("LOG_LEVEL", "INFO").upper())
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        self.logger = logging.getLogger("xmlrpc-homematic")
        self.server_logger = logging.getLogger("server")
        self.client_logger = logging.getLogger("client")
        self.server_logger.setLevel(log_level)
        self.client_logger.setLevel(log_level)

    def setup(self) -> None:
        """Initialize server and clients."""
        logging.debug("Starting setup...")
        device_tuple = self._convert_to_tuple("HM_DEVICES")
        clients_tuple = self._convert_to_tuple("SUBSCRIBE_TO")
        logging.debug(f"Devices: {device_tuple}, Clients: {clients_tuple}")
        ccu = [
            self.CCU_TYPES[client]
            for client in clients_tuple
            if client in self.CCU_TYPES
        ]
        self._setup_server(device_tuple)
        self._setup_client(ccu)

    def _setup_server(self, device_tuple) -> None:
        """Initialize XML-RPC server."""
        self.server = XMLRPCServer(
            host=self.config["SERVER_IP"],
            port=int(self.config["SERVER_PORT"]),
            logger=self.server_logger,
            ccu_device_ids=device_tuple,
            db_file=self.config["DB_FILE"],
            allowed_clients=self._convert_to_tuple("ALLOWED_CLIENTS"),
            server_id="xmlrpc-server",
            ccu_parameters=self._convert_to_tuple("CCU_PARAMETERS"),
            state_device_ids=self._convert_to_tuple("STATE_DEVICE_IDS"),
        )

    def _setup_client(self, ccu) -> HTTPClient:
        """Create and configure HTTP client."""
        self.client = HTTPClient(
            ccu=ccu,
            xmlRpcServer=f"{self.config['SERVER_IP']}:{self.config['SERVER_PORT']}",
            username=self.config["HM_USERNAME"],
            password=self.config["HM_PASSWORD"],
            logger=self.client_logger,
        )

    def start_watchdog(self):
        """Start watchdog notification thread."""

        def _watchdog_notify():
            while not self._shutdown_event.is_set():
                watchdog()
                time.sleep(15)  # Half of WatchdogSec

        self._watchdog_thread = threading.Thread(target=_watchdog_notify, daemon=True)
        self._watchdog_thread.start()

    def stop_watchdog(self):
        """Stop watchdog notification thread."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._shutdown_event.set()
            self._watchdog_thread.join(timeout=2.0)


@contextmanager
def lifespan(app: XMLRPC_HOMEMATIC):
    """Manage application lifecycle with systemd notifications."""
    try:
        logging.info("=============== Initializing application... ===============")
        status("Initializing application...")
        app.setup()

        logging.debug("=============== Starting XML-RPC server... ===============")
        status("Starting XML-RPC server...")
        app.server.start()
        time.sleep(app.STARTUP_DELAY)

        logging.info("================== Registering clients... =================")
        status("Registering clients...")
        app.client.register_all()

        # Start watchdog and notify systemd we're ready
        app.start_watchdog()
        ready()
        status("Running")

        logging.info("========== Setup complete, entering main loop... ==========")
        yield

    except Exception as e:
        logging.error(f"Error during startup: {e}", exc_info=True)
        status(f"Error: {str(e)}")
        raise

    finally:
        logging.info("================= Graceful shutdown... ==================")
        status("Shutting down...")
        stopping()
        app.stop_watchdog()

        try:
            app.client.unregister_all()
        except Exception as e:
            logging.error(f"Error unregistering client: {e}")
        if app.server:
            app.server.stop()


def main():
    try:
        app = XMLRPC_HOMEMATIC()
    except Exception as e:
        logging.error(f"Failed to initialize application: {e}", exc_info=True)
        sys.exit(1)

    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))

    try:
        with lifespan(app):
            try:
                while not app._shutdown_event.is_set():
                    time.sleep(1)
            except KeyboardInterrupt:
                app._shutdown_event.set()
    except Exception as e:
        logging.error(f"Application failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
