import threading, json
from xmlrpc.server import SimpleXMLRPCServer
from datetime import datetime
from threading import Lock


class xmlrpcServer:
    def __init__(self, host, port, logger, DEVICE_TUPLE, server_id=None):
        self.logger = logger
        self.logger.debug(f"Initializing XML-RPC server {server_id} on {host}:{port}")
        self.host = host
        self.port = port
        self.logger = logger
        self.server = SimpleXMLRPCServer((self.host, self.port))
        self.server.register_instance(self)
        self.server.register_multicall_functions()
        self.server_thread = None
        self.DEVICE_TUPLE = DEVICE_TUPLE
        self.log_file = "test_log.log"
        self.server_id = server_id or f"{host}:{port}"
        self._log_lock = Lock()  # Add thread-safe logging

    def _args_workflow(self, args, event):
        response = self._parse_args_to_dict(args)
        self.logger.info(f"XML-RPC {event}: {response}")
        mysql = self._process_refactored_args(response)

        if mysql:
            self._write_to_log(response)
        return

    def _parse_args_to_dict(self, args):
        return {
            "channel": args[1],
            "param": args[2],
            "value": args[3],
        }

    def _process_refactored_args(self, refactored_args):
        channel = refactored_args["channel"]
        device_id = channel.split(":")[0] if ":" in channel else channel

        if device_id not in self.DEVICE_TUPLE:
            return False

        return True

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

    def event(self, *args):
        self._args_workflow(args, "Event")
        return ""

    def listDevices(self, *args):
        self.logger.debug("=== XML-RPC listDevice ===")
        for arg in args:
            self.logger.debug(arg)
        self.logger.debug("===========================")
        return []

    def newDevices(self, *args):
        self.logger.debug("=== XML-RPC newDevices ===")
        self.logger.debug("scipping args")
        self.logger.debug("===========================")
        return ""

    def newDevice(self, *args):
        self._args_workflow(args, "newDevice")
        return ""

    def start(self):
        self.logger.debug(f"Starting server thread for {self.server_id}")
        try:
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
            self.logger.info(f"Server {self.server_id} started successfully")
        except Exception as e:
            self.logger.error(
                f"Failed to start server {self.server_id}: {e}", exc_info=True
            )
            raise

    def stop(self):
        self.logger.info(f"Stopping XML-RPC server")
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join()
