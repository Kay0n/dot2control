import asyncio
import aiohttp
import json
import hashlib
from typing import Optional, Dict, Any, Callable, List






class ConnectionHandler:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.address: Optional[str] = None
        self.password: Optional[str] = None
        self._connecting = False
        self.connected = False
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session_id: Optional[str] = None
    
    async def connect(self, address: str, password: str):
        if self._connecting or self.connected:
            raise RuntimeError("Currently initializing or already initialized")
        self._connecting = True
        self.connected = False
        self.address = address
        self.password = hashlib.md5(password.encode("utf-8")).hexdigest()
        try:
            self.session = aiohttp.ClientSession()
            self.ws = await self.session.ws_connect(f"ws://{self.address}/?ma=1")
            async for message in self.ws:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    if "status" in data:
                        await self.send({"session": 0})
                    if "session" in data:
                        self.session_id = data["session"]
                    if "forceLogin" in data:
                        await self._login()
                    if "responseType" in data:
                        self.connected = True
                        break
                    await asyncio.sleep(0.01)

        except Exception as e:
            if self.session:
                await self.session.close()
            raise ConnectionError(f"Failed to connect to dot2: {str(e)}")
        finally:
            self._connecting = False
    

    async def disconnect(self):
        if self.connected and self.session_id:
            await self.send({"requestType": "close", "session": self.session_id})
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.session and not self.session.closed:
            await self.session.close()
        self.connected = False
        self.session_id = None


    async def _login(self):
        if not self.session_id:
            raise RuntimeError("Session ID not set")
        await self.send({
            "requestType": "login",
            "username": "remote",
            "password": self.password,
            "session": self.session_id,
        })

    async def send(self, payload: Dict[str, Any]):
        if not self.ws:
            raise RuntimeError("WebSocket connection not established")
        await self.ws.send_str(json.dumps(payload, separators=(',', ':')))

    def is_connected(self) -> bool:
        return self.connected

    def get_session_id(self) -> int:
        return self.session_id

    def get_messages(self):
        return self.ws