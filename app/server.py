import threading
import logging
import requests
from requests.exceptions import RequestException
from typing import Optional, Dict, Any, Tuple, List
from xmlrpc.server import SimpleXMLRPCServer
from threading import Lock

from db import Database


class XMLRPCServer:
    """HomeMatic XML-RPC Server implementation."""

    # Class constants
    CCU_PARAMETER_LIST = (
        "WINDOW_STATE",
        "OPERATING_VOLTAGE",
        "SET_POINT_TEMPERATURE",
        "ACTUAL_TEMPERATURE",
        "LEVEL",
        "BOOST_MODE",
        "ACTIVE_PROFILE",
    )
    STATE_URL = "http://localhost:82"
    REQUEST_TIMEOUT = 10

    def __init__(
        self,
        host: str,
        port: int,
        logger: logging.Logger,
        ccu_device_ids: Tuple[str, ...],
        db_file: str,
        server_id: Optional[str] = None,
        ccu_parameters: Optional[Tuple[str]] = None,
        state_device_ids: Optional[List[str]] = None,
    ) -> None:
        self.logger = logger
        self.host = host
        self.port = port
        self.ccu_device_ids = ccu_device_ids
        self.db_file = db_file
        self.server_id = server_id or f"{host}:{port}"
        self.ccu_parameters = ccu_parameters or self.CCU_PARAMETER_LIST
        self.state_device_ids = state_device_ids
        self._device_states = {}
        self.database = Database(db_file=self.db_file, logger=logging.getLogger("db"))
        self._log_lock = Lock()

        # Disable built-in logging
        logging.getLogger("xmlrpc.server").setLevel(logging.CRITICAL)

        # Initialize XML-RPC server
        self.logger.debug(f"Initializing XML-RPC server {server_id} on {host}:{port}")
        self.server = SimpleXMLRPCServer((self.host, self.port), logRequests=False)
        self.server.register_instance(self)
        self.server.register_multicall_functions()
        self.server_thread: Optional[threading.Thread] = None

    def __enter__(self) -> "XMLRPCServer":
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.stop()

    def _main(self, args: tuple, event: str) -> bool:
        """Process incoming XML-RPC arguments."""
        keys = ["interface", "deviceID", "param", "value"]
        response = dict(zip(keys, args))
        self.logger.info(f"XML-RPC {event}: {response}")

        """Process states update and database insertion."""
        if self._get_device_id(response):
            if len(args) == 4:
                if (
                    self.state_device_ids
                    and response["deviceID"] in self.state_device_ids
                ):
                    self._update_device_state(response)
                elif self.ccu_parameters and response["param"] in self.ccu_parameters:
                    self._update_device_state(response)

                if response["param"] == "WINDOW_STATE":
                    self._notify_states(response)

                return self._insert_into_db(response)

        return False

    def _get_device_id(self, refactored_args: Dict[str, Any]) -> bool:
        """Validate and process refactored arguments."""
        if "deviceID" not in refactored_args:
            return False

        d = refactored_args["deviceID"]
        device_id = d.split(":")[0] if ":" in d else d

        return device_id in self.ccu_device_ids

    def _insert_into_db(self, data: Dict[str, Any]) -> bool:
        """Insert or update device data in SQLite database."""
        try:
            self.database.connect()
            self.database._create_device_table()
            query = """
                INSERT INTO devices (interface, device_id, param, value, timestamp)
                VALUES (?, ?, ?, ?, strftime('%Y-%m-%d %H:%M:%f', 'now'))
                ON CONFLICT(device_id, param) 
                DO UPDATE SET
                    value = excluded.value,
                    interface = excluded.interface,
                    timestamp = strftime('%Y-%m-%d %H:%M:%f', 'now');
            """
            params = (data["interface"], data["deviceID"], data["param"], data["value"])
            self.database.execute(query, params)
            self.logger.debug(f"Data upserted into database: {data}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to upsert data into database: {e}")
            return False
        finally:
            self.database.close()

    def _update_device_state(self, data: Dict[str, Any]) -> bool:
        """Update device state in memory."""
        self.logger.debug(f"Received state change: {data}")
        try:
            if data["deviceID"] not in self._device_states:
                self._device_states[data["deviceID"]] = {}
            self._device_states[data["deviceID"]][data["param"]] = data["value"]
            self.logger.debug(
                f"{data['deviceID']} {data['param']} changed to: {data['value']}"
            )
            self.logger.debug(f"Device states: {self._device_states}")
            return True
        except RequestException as e:
            self.logger.error(f"Error notifying window state: {e}")
            return False

    def _notify_states(self, data: Dict[str, Any]) -> bool:
        """Notify window state change via GET request."""
        self.logger.debug(f"Received 'Window_STATE' change: {data}")
        try:
            response = requests.get(
                self.STATE_URL,
                params={"window_state": data["deviceID"]},
                timeout=self.REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except RequestException as e:
            self.logger.error(f"Error notifying window state: {e}")
            return False

    # CCU XML-RPC methods
    def event(self, *args) -> str:
        self._main(args, "Event")
        return ""

    def listDevices(self, *args) -> list:
        self._main(args, "listDevices")
        return []

    def newDevices(self, *args) -> str:
        self.logger.debug("XML-RPC newDevices: skipping args - too verbose")
        return ""

    def newDevice(self, *args) -> str:
        self._main(args, "newDevice")
        return ""

    def listMethods(self, *args) -> str:
        self._main(args, "listMethods")
        return ""

    def setReadyConfig(self, *args) -> list:
        self._main(args, "setReadyConfig")
        return []

    # Custom methods to interact with the server
    def get_device_states(self, device) -> Dict[str, Dict[str, Any]]:
        """Return device states."""
        return self._device_states[device] if device in self._device_states else {}

    def get_all_device_states(self) -> Dict[str, Dict[str, Any]]:
        """Return all device states."""
        return self._device_states

    # Server lifecycle methods
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
