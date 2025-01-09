import uuid
import base64
from xmlrpc import client


class xmlrpcClient:
    def __init__(
        self,
        hmServers: tuple,
        xmlRpcServers: tuple,
        username: str,
        password: str,
        idHm: str,
        logger,
    ):
        self.logger = logger
        self.hmServers: tuple = hmServers
        self.xmlRpcServers: tuple = xmlRpcServers
        self.username: str = username
        self.password: str = password
        self.idHm = {}  # Dictionary to store UUIDs for each server
        self.proxies = []
        self.logger.debug(f"Initialized client with servers: {hmServers}")

    def _register(self, hmServer, server):
        self.logger.debug(f"Registering with HomeMatic CCU at {hmServer}")
        try:
            proxy = self._get_authenticated_proxy(hmServer)
            # Generate unique UUID for each server
            self.idHm[hmServer] = self._createUUID()
            proxy.init(server, self.idHm[hmServer])
            self.proxies.append(proxy)  # Store the proxy
            self.logger.debug(
                f"Registration successful with UUID: {self.idHm[hmServer]}"
            )
        except Exception as e:
            self.logger.error(f"Registration failed: {str(e)}")
            raise

    def _createUUID(self) -> str:
        uuid_str = str(uuid.uuid4())
        self.logger.debug(f"Generated UUID: {uuid_str}")
        return uuid_str

    def _get_authenticated_proxy(self, hmServer):
        """Create an authenticated XML-RPC proxy"""
        auth = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
        headers = [
            ("Authorization", f"Basic {auth}"),
            ("Content-Type", "text/xml"),
        ]
        return client.ServerProxy(f"http://{hmServer}", headers=headers)

    def _unregister(self, hmServer, server):
        self.logger.debug(f"Unregistering from HomeMatic CCU at {hmServer}")
        try:
            proxy = self._get_authenticated_proxy(hmServer)
            proxy.init(server, "")
            self.logger.debug("Unregistration successful")
        except Exception as e:
            self.logger.error(f"Unregistration failed: {str(e)}")
            # Don't raise here to allow clean shutdown

    def register(self):
        for i in range(len(self.hmServers)):
            self._register(self.hmServers[i], self.xmlRpcServers[i])

    def unregister(self):
        for i in range(len(self.hmServers)):
            self._unregister(self.hmServers[i], "")
