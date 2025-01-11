import requests
import base64
import uuid
from typing import Optional
from logging import Logger


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
        hmServer: str,
        xmlRpcServer: str,
        username: str,
        password: str,
        idHM: str,
        logger: Logger,
    ) -> None:
        self.hmServer: str = hmServer
        self.xmlRpcServer: str = xmlRpcServer
        self.username: str = username
        self.password: str = password
        self.idHM: Optional[str] = idHM
        self.logger: Logger = logger

        self.logger.debug(f"Initialized client with server: {hmServer}")

    def _create_request_body(self, method: str, client_id: str = "") -> str:
        """Create XML request body."""
        return self.XML_TEMPLATE.format(
            method=method, server=f"http://{self.xmlRpcServer}", client_id=client_id
        )

    def _basic_auth(self):
        return base64.b64encode(f"{self.username}:{self.password}".encode()).decode()

    def _make_request(self, body: str) -> requests.Response:
        """Make HTTP request with error handling."""
        headers = {
            "Content-Type": self.CONTENT_TYPE,
            "Authorization": f"Basic {self._basic_auth()}",
        }

        response = requests.post(
            url=self.hmServer, headers=headers, data=body, timeout=self.TIMEOUT
        )
        response.raise_for_status()
        return response

    def register(self) -> None:
        """Register client with HomeMatic CCU."""
        self.logger.debug(f"Registering with HomeMatic CCU at {self.hmServer}")
        try:
            self.idHM = self._createUUID() if not self.idHM else self.idHM
            body = self._create_request_body("init", self.idHM)
            response = self._make_request(body)

            if response.status_code == 200:
                self.logger.info(
                    f"Registration successful with UUID: {self.idHM}, "
                    f"server: {self.xmlRpcServer} at {self.hmServer}"
                )
        except requests.RequestException as e:
            self.logger.error(f"Registration failed: {str(e)}")
            raise

    def unregister(self) -> None:
        """Unregister client from HomeMatic CCU."""
        self.logger.debug(f"Unregistering from HomeMatic CCU at {self.hmServer}")
        try:
            body = self._create_request_body("init", "")
            response = self._make_request(body)

            if response.status_code == 200:
                self.logger.info(
                    f"Unregistration clientID: {self.idHM}, "
                    f"successful with Homematic CCU at {self.hmServer}"
                )
        except requests.RequestException as e:
            self.logger.error(f"Unregistration failed: {str(e)}")
