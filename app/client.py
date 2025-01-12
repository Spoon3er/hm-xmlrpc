import requests
import base64
import logging


class HTTPClient:
    """HTTP client for HomeMatic CCU communication."""

    # Class constants
    CONTENT_TYPE = "application/xml"
    TIMEOUT = 15
    XML_TEMPLATE = """
        <methodCall>
            <methodName>{method}</methodName>
            <params>
                <param><value><string>{server}</string></value></param>
                <param><value><string>{client_id}</string></value></param>
            </params>
        </methodCall>
    """.strip()

    def __init__(
        self,
        ccu: list,
        xmlRpcServer: str,
        username: str,
        password: str,
        logger: logging.Logger,
    ) -> None:
        self.ccu = ccu
        self.xmlRpcServer = xmlRpcServer
        self.username = username
        self.password = password
        self.logger = logger

        self.logger.debug(f"Initialized client with server: {self.ccu}")

    def _create_request_body(self, method: str, client_id: str = "") -> str:
        """Create XML request body."""
        return self.XML_TEMPLATE.format(
            method=method, server=f"http://{self.xmlRpcServer}", client_id=client_id
        )

    def _basic_auth(self) -> str:
        return base64.b64encode(f"{self.username}:{self.password}".encode()).decode()

    def _make_request(self, body: str, url: str) -> requests.Response:
        """Make HTTP request with error handling."""
        headers = {
            "Content-Type": self.CONTENT_TYPE,
            "Authorization": f"Basic {self._basic_auth()}",
        }
        response = requests.post(
            url=url, headers=headers, data=body, timeout=self.TIMEOUT
        )
        response.raise_for_status()
        return response

    def _register(self, client: dict) -> None:
        """Register client with HomeMatic CCU."""
        self.logger.debug(
            f"Registering {client['register_id']} with HomeMatic CCU at {client['url']}"
        )
        try:
            body = self._create_request_body("init", client["register_id"])
            response = self._make_request(body, client["url"])

            if response.status_code == 200:
                self.logger.info(
                    f"Registration successful with clientID: {client['register_id']}, "
                    f"server: {self.xmlRpcServer} at {client['url']}"
                )
        except requests.RequestException as e:
            self.logger.error(f"Registration failed: {str(e)}")
            raise

    def _unregister(self, client: dict) -> None:
        """Unregister client from HomeMatic CCU."""
        self.logger.debug(f"Unregistering from HomeMatic CCU at {client['url']}")
        try:
            body = self._create_request_body("init", "")
            response = self._make_request(body, client["url"])

            if response.status_code == 200:
                self.logger.info(
                    f"Unregistration clientID: {client['register_id']}, "
                    f"successful with Homematic CCU at {client['url']}"
                )
        except requests.RequestException as e:
            self.logger.error(f"Unregistration failed: {str(e)}")

    def register_all(self) -> None:
        """Register all clients with HomeMatic CCU."""
        for client in self.ccu:
            self._register(client)

    def unregister_all(self) -> None:
        """Unregister all clients from HomeMatic CCU."""
        for client in self.ccu:
            self._unregister(client)
