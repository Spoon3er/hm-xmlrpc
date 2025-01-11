import threading, json, logging
from typing import Optional, Dict, Any, Tuple, List
from xmlrpc.server import SimpleXMLRPCServer
from datetime import datetime
from threading import Lock


class XMLRPCServer:
    """HomeMatic XML-RPC Server implementation."""

    # Class constants
    METHODS = [
        "event",
        "listDevices",
        "newDevices",
        "newDevice",
        "listMethods",
        "setReadyConfig",
    ]
    DEFAULT_LOG_FILE = "test_log.log"

    def __init__(
        self,
        host: str,
        port: int,
        logger: logging.Logger,
        device_tuple: Tuple[str, ...],
        server_id: Optional[str] = None,
    ) -> None:
        self.logger = logger
        self.host = host
        self.port = port
        self.device_tuple = device_tuple
        self.server_id = server_id or f"{host}:{port}"
        self.log_file = self.DEFAULT_LOG_FILE
        self._log_lock = Lock()

        # Disable built-in logging
        logging.getLogger("xmlrpc.server").setLevel(logging.CRITICAL)

        # Initialize XML-RPC server
        self.logger.debug(f"Initializing XML-RPC server {server_id} on {host}:{port}")
        self.server = SimpleXMLRPCServer((self.host, self.port), logRequests=False)
        self.server.register_instance(self)
        self.server.register_multicall_functions()
        self.server_thread: Optional[threading.Thread] = None

    def _args_workflow(self, args: tuple, event: str) -> bool:
        """Process incoming XML-RPC arguments."""
        keys = ["clientID", "channel", "param", "value"]
        response = dict(zip(keys, args))
        self.logger.info(f"XML-RPC {event}: {response}")

        if self._process_refactored_args(response):
            return self._write_to_log(response)
        return False

    def _process_refactored_args(self, refactored_args: Dict[str, Any]) -> bool:
        """Validate and process refactored arguments."""
        if "channel" not in refactored_args:
            return False

        channel = refactored_args["channel"]
        device_id = channel.split(":")[0] if ":" in channel else channel

        return device_id in self.device_tuple

    def __enter__(self) -> "XMLRPCServer":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

    def _write_to_log(self, data):
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "server_id": self.server_id,
                "data": data,
            }

            with self._log_lock:  # Thread-safe file writing
                with open(self.log_file, "a") as f:
                    json.dump(log_entry, f)
                    f.write("\n")
            self.logger.debug(f"Server {self.server_id} logged data to {self.log_file}")
            return True
        except Exception as e:
            self.logger.error(f"Server {self.server_id} failed to write to log: {e}")
            return False

    def event(self, *args) -> str:
        self._args_workflow(args, "Event")
        return ""

    def listDevices(self, *args) -> List:
        self._args_workflow(args, "listDevices")
        return []

    def newDevices(self, *args) -> str:
        self.logger.info("XML-RPC newDevices: scipping args due to overhauling")
        return ""

    def newDevice(self, *args) -> str:
        self._args_workflow(args, "newDevice")
        return ""

    def listMethods(self, *args) -> str:
        self._args_workflow(args, "listMethods")
        return ""

    def setReadyConfig(self, *args) -> List:
        self._args_workflow(args, "setReadyConfig")
        return []

    def start(self) -> None:
        """Start the XML-RPC server in a separate thread."""
        self.logger.debug(f"Starting server thread for {self.server_id}")
        try:
            self.server_thread = threading.Thread(
                target=self.server.serve_forever, name=f"XMLRPCServer-{self.server_id}"
            )
            self.server_thread.daemon = True
            self.server_thread.start()
            self.logger.info(f"Server {self.server_id} started successfully")
        except Exception as e:
            self.logger.error(
                f"Failed to start server {self.server_id}: {e}", exc_info=True
            )
            raise

    def stop(self) -> None:
        """Stop the XML-RPC server and cleanup resources."""
        self.logger.info(f"Stopping XML-RPC server")
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5.0)
