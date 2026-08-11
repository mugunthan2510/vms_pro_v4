import logging
from typing import List, Callable, Dict, Any
from SmartApi import SmartConnect

logger = logging.getLogger("SmartStream")

class SmartApiStreamManager:
    def __init__(self, api_key: str, client_code: str, password: str, totp_secret: str):
        self.api_key = api_key
        self.client_code = client_code
        self.password = password
        self.totp_secret = totp_secret
        
        self.smart_api = SmartConnect(api_key=self.api_key)
        self.sws = None
        self.feed_token = None
        self.jwt_token = None
        self.tick_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    # FIX: Added 'self' parameter here
    def authenticate(self) -> bool:
        """
        Authenticates with Angel One REST API using TOTP and fetches JWT/Feed Tokens.
        """
        try:
            import pyotp
            totp = pyotp.TOTP(self.totp_secret).now()
            session = self.smart_api.generateSession(self.client_code, self.password, totp)
            
            if session.get('status'):
                self.jwt_token = session['data']['jwtToken']
                self.feed_token = self.smart_api.getfeedToken()
                logger.info("Smart API Login & Feed Token Generation Successful!")
                return True
            else:
                logger.error(f"Login failed: {session.get('message')}")
                return False
        except Exception as e:
            logger.error(f"Authentication exception: {e}")
            return False

    # FIX: Correctly registered instance method with 'self'
    def add_tick_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Register custom callbacks (e.g., UI broadcast or Engine pipeline)"""
        self.tick_callbacks.append(callback)

    def _on_data(self, wsapp, message):
        """Triggered on receiving live ticks from SmartAPI Socket"""
        logger.debug(f"Tick received: {message}")
        for callback in self.tick_callbacks:
            try:
                callback(message)
            except Exception as err:
                logger.error(f"Error executing callback: {err}")

    def _on_open(self, wsapp):
        logger.info("SmartAPI WebSocket Connected!")

    def _on_error(self, wsapp, error):
        logger.error(f"SmartAPI WebSocket Error: {error}")

    def _on_close(self, wsapp):
        logger.warning("SmartAPI WebSocket Connection Closed.")

    def start_stream(self, tokens_list: List[str], exchange_type: int = 1, mode: int = 1):
        """
        Starts WebSocket connection and subscribes to given tokens.
        """
        try:
            from SmartApi.smartWebSocketV2 import SmartWebSocketV2
        except ImportError:
            logger.error("SmartWebSocketV2 not found in SmartApi package.")
            return

        if not self.jwt_token or not self.feed_token:
            if not self.authenticate():
                logger.error("Cannot start stream without valid authentication tokens.")
                return

        # Initialize WebSocket V2
        self.sws = SmartWebSocketV2(
            auth_token=self.jwt_token,
            api_key=self.api_key,
            client_code=self.client_code,
            feed_token=self.feed_token
        )

        # Assign Event Handlers
        self.sws.on_open = self._on_open
        self.sws.on_data = self._on_data
        self.sws.on_error = self._on_error
        self.sws.on_close = self._on_close

        # Subscription structure
        token_payload = [
            {
                "exchangeType": exchange_type,
                "tokens": tokens_list
            }
        ]
        
        # Connect & Subscribe
        self.sws.connect()
        correlation_id = "vms_pro_stream_01"
        self.sws.subscribe(correlation_id, mode, token_payload)
        logger.info(f"Subscribed to tokens: {tokens_list} on mode {mode}")