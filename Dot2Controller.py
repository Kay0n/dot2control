import asyncio
import aiohttp
import json
import hashlib
from enum import Enum
from typing import Optional, Dict, Any, Callable, List



class Dot2Controller:
    def __init__(self):
        self.address: Optional[str] = None
        self.password: Optional[str] = None
        self.task_list = []
        self.connected = False
        self.fader_event_listeners: List[Callable] = []
        self.button_event_listeners: List[Callable] = []
        self.button_states = {}
        self.fader_states = {}
        self.client_session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session_id: Optional[str] = None
        self.reconnect_interval = 5  # seconds
        self.keep_alive_interval = 15  # seconds

   
    async def connect(self, address: str, password: str):
        self.address = address
        self.password = hashlib.md5(password.encode()).hexdigest()
        await self._connect()
        self.task_list.append(asyncio.create_task(self._keep_alive()))

    async def _connect(self):
        try:
            if self.client_session and not self.client_session.closed:
                await self.client_session.close()
            self.client_session = aiohttp.ClientSession()
            self.ws = await self.client_session.ws_connect(f"ws://{self.address}/?ma=1")
            self.task_list.append(asyncio.create_task(self.process_messages()))
            while not self.connected:
                await asyncio.sleep(0.1)
            print("Connected to Dot2")
        except Exception as e:
            print(f"Connection error: {e}")
            await asyncio.sleep(self.reconnect_interval)
            await self._connect()

    async def _keep_alive(self):
        while True:
            await asyncio.sleep(self.keep_alive_interval)
            if self.connected and self.ws and not self.ws.closed:
                try:
                    await self.send({"session": self.session_id})
                except Exception as e:
                    print(f"Keep-alive error: {e}")
                    self.connected = False
                    await self._connect()

        



    async def process_messages(self):
        while True:
            try:
                async for message in self.ws:          
                    if message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        print(f"WebSocket closed or error: {message.data}")
                        break

                    if message.type != aiohttp.WSMsgType.TEXT:
                        print(f"Unexpected message type: {message.type}")
                        continue

                    data = json.loads(message.data)
                    
                    if data.get("responseType") == "login":
                        if data.get("result"):
                            print("Logged in successfully")
                            self.connected = True
                            await self.request_playbacks()
                        else:
                            print("Login failed")
                            break

                    if data.get("responseType") == "playbacks":
                        await self.process_playback(data)
                        await self.request_playbacks()
                    
                    if data.get("session"):
                        print(f"Session ID: {data.get('session')}")
                        print(data)
                        self.session_id = data.get("session")
                    
                    if data.get("forceLogin") == True:
                        print("Sending user credentials")
                        await self._login()
                    
                    if data.get("status") and data.get("appType"):
                        print("Connection Established!")
                        await self.send({"session": 0})

            except Exception as e:
                print(f"Error in process_messages: {e}")
            finally:
                self.connected = False
                await self._connect()


    async def process_playback(self, data):
        if "itemGroups" not in data:
            return

        def extract_executors(item_groups):
            for group in item_groups:
                executor_type = group.get("itemsType")
                if executor_type not in (2, 3):
                    continue
                for item in (item for item_list in group.get("items", []) for item in item_list):
                    executor = {
                        "id": item.get("iExec"),
                        "is_active": item.get("isRun", 0) == 1
                    }
                    if executor_type == 2:  # fader
                        executor["position"] = 0
                        for block in item.get("executorBlocks", []):
                            if "fader" in block:
                                executor["position"] = block["fader"].get("v", 0)
                                break
                    yield executor_type, executor # testing yield

        def update_state(state_dict, executor, key):
            state = state_dict.get(executor["id"], {})
            changed = any(state.get(k) != executor[k] for k in key)
            if changed:
                state_dict[executor["id"]] = {k: executor[k] for k in key}
            return changed

        for executor_type, executor in extract_executors(data["itemGroups"]):
            if executor_type == 2:  # fader
                if update_state(self.fader_states, executor, ["position", "is_active"]):
                    for listener in self.fader_event_listeners:
                        listener(executor["id"], executor["is_active"], executor["position"])
                       
            else:  # button
                if update_state(self.button_states, executor, ["is_active"]):
                    for listener in self.button_event_listeners:
                        listener(executor["id"], executor["is_active"])
        

    async def disconnect(self):
        for task in self.task_list:
            if task:
                task.cancel()
        if self.session_id:
            await self.send({"requestType": "close", "session": self.session_id})
        if self.ws and not self.ws.closed:
            await self.ws.close()
        if self.client_session and not self.client_session.closed:
            await self.client_session.close()
        self.session_id = None
        self.connected = False
        print("Disconnected from Dot2")


    async def send(self, payload: Dict[str, Any]):
        try:
            if not self.ws:
                raise RuntimeError("WebSocket connection not established")
            await self.ws.send_str(json.dumps(payload, separators=(',', ':')))
        except Exception as e:
            print(e)
    


    async def _login(self):
        if not self.session_id:
            raise RuntimeError("Session ID not set")
        payload = {
            "requestType": "login",
            "username": "remote",
            "password": self.password,
            "session": self.session_id,
        }
        await self.send(payload)


    async def send_command(self, command: str):
        await self.send({
            "requestType": "command",
            "command": command,
            "session": self.session_id
        })


    async def set_fader(self, executor_number: int, normalized_position: float):
        command = f"Executor {executor_number} At {normalized_position * 100}"
        await self.send_command(command)


    def add_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.append(callback)


    def remove_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.remove(callback)


    async def request_playbacks(self):
        if not self.session_id:
            return
        payload = {
            "requestType": "playbacks",
            "startIndex": [0,100,200],
            "itemsCount": [13,13,13],
            "pageIndex": 0,     
            "itemsType": [2,3,3],       # fader, button, button (I think)
            "view": 2,                  # fader view
            "execButtonViewMode": 1,    # non-extended, 2?
            "buttonsViewMode": 0,
            "session": self.session_id,
            "maxRequests": 1
        }
        await self.send(payload)
