import time, logging, signal, sys, threading
from contextlib import contextmanager
from dotenv import dotenv_values
from typing import Optional
from server import xmlrpcServer
from client import xmlrpcClient

config = dotenv_values(".env")
log_level = getattr(logging, config.get("LOG_LEVEL", "INFO").upper())
print(config)

logging.basicConfig(
    level=log_level,  # Force DEBUG level temporarily for troubleshooting
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class XMLRPC_HOMEMATIC:
    def __init__(self):
        self.config = config
        self.server_hmIp: Optional[xmlrpcServer] = None
        self.server_virtualDevices: Optional[xmlrpcServer] = None
        self.client: Optional[xmlrpcClient] = None
        self.server_logger = logging.getLogger("server")
        self.server_logger.setLevel(log_level)  # Ensure DEBUG level here too
        self.client_logger = logging.getLogger("client")
        self.client_logger.setLevel(log_level)

    def setup(self):
        self.server_logger.debug("Starting setup...")
        # Parse DEVICE_TUPLE from comma-separated string
        device_tuple = tuple(self.config.get("HM_DEVICES", "").strip().split(","))
        self.server_logger.debug(f"Parsed device tuple: {device_tuple}")

        # Initialize servers with IDs
        self.server_hmIp = xmlrpcServer(
            host=self.config["SERVER_HMIP_IP"],
            port=int(self.config["SERVER_HMIP_PORT"]),
            logger=self.server_logger,
            DEVICE_TUPLE=device_tuple,
            server_id="hmip",
        )

        self.server_virtualDevices = xmlrpcServer(
            host=self.config["SERVER_VIRTUALDEVICES_IP"],
            port=int(self.config["SERVER_VIRTUALDEVICES_PORT"]),
            logger=self.server_logger,
            DEVICE_TUPLE=device_tuple,
            server_id="virtual",
        )

        # Initialize client
        severURLs = (
            f"{self.config['SERVER_HMIP_IP']}:{self.config['SERVER_HMIP_PORT']}",
            f"{self.config['SERVER_VIRTUALDEVICES_IP']}:{self.config['SERVER_VIRTUALDEVICES_PORT']}",
        )
        hmServers = (
            self.config["HM_SERVER_HMIP"],
            self.config["HM_SERVER_VIRTUALDEVICES"],
        )
        self.client = xmlrpcClient(
            hmServers=hmServers,
            xmlRpcServers=severURLs,
            username=self.config["HM_USERNAME"],
            password=self.config["HM_PASSWORD"],
            idHm="",
            logger=self.client_logger,
        )
        self.server_logger.debug("Setup completed")


@contextmanager
def lifespan(app: XMLRPC_HOMEMATIC):
    try:
        logging.debug("Initializing application...")
        app.setup()

        logging.debug("Starting HM-IP server...")
        app.server_hmIp.start()
        time.sleep(1)  # Give first server time to start

        logging.debug("Starting Virtual Devices server...")
        app.server_virtualDevices.start()
        time.sleep(1)  # Give second server time to start

        logging.debug("Registering client...")
        app.client.register()
        logging.debug("Setup complete, entering main loop...")

        yield
    except Exception as e:
        logging.error(f"Error during startup: {e}", exc_info=True)
        raise
    finally:
        logging.debug("Shutting down...")
        if app.client:
            app.client.unregister()
        if app.server_hmIp:
            app.server_hmIp.stop()
        if app.server_virtualDevices:
            app.server_virtualDevices.stop()


def signal_handler(sig, frame):
    print("\nCtrl+C pressed. Exiting...")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, signal_handler)
    app = XMLRPC_HOMEMATIC()

    with lifespan(app):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
