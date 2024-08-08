import asyncio
import aiohttp
import json
import hashlib
from enum import IntEnum
from typing import Optional, Dict, Any, Callable, List
import dataclasses



class ExecutorType(IntEnum):
    BUTTON = 3
    FADER = 2



@dataclasses.dataclass
class ExecutorGroup:
    start_index: int
    count: int
    executor_type: ExecutorType



class Dot2Controller:
    def __init__(self):
        self.address: Optional[str] = None
        self._password: Optional[str] = None
        self.tasks = []
        self.connected = False
        self.fader_event_listeners: List[Callable] = []
        self.button_event_listeners: List[Callable] = []
        self.button_states = {}
        self.fader_states = {}
        self.executor_config = {}
        self.client_session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.session_id: Optional[str] = None
        self.keep_alive_interval = 15  # seconds
        self.timeout = 10  # 10 seconds timeout

   
    async def connect(self, address: str, password: str) -> bool:
        self.address = address
        self._password = hashlib.md5(password.encode()).hexdigest()
        try:
            await self.__connect()
        except Exception as e:
            raise(f"Connection error: {e}")
        

    async def __connect(self):

        if self.client_session and not self.client_session.closed:
            await self.client_session.close()
        self.client_session = aiohttp.ClientSession()
        self.ws = await self.client_session.ws_connect(f"ws://{self.address}/?ma=1")
        self.tasks.append(asyncio.create_task(self.__task_wrapper(self.__process_messages)))
        await self.__wait_for_connection()
        self.tasks.append(asyncio.create_task(self.__task_wrapper(self.__keep_alive)))
        

    async def __wait_for_connection(self) -> None:
        for _ in range(self.timeout * 10): 
            if self.connected:
                return
            await asyncio.sleep(0.1)
        raise TimeoutError("Connection timeout")


    async def __login(self):
        if not self.session_id:
            raise RuntimeError("Session ID not set")
        payload = {
            "requestType": "login",
            "username": "remote",
            "password": self._password,
            "session": self.session_id,
        }
        await self.send(payload)


    async def disconnect(self):
        for task in self.tasks:
            if task: task.cancel()
          
        if self.session_id:
            await self.send({"requestType": "close", "session": self.session_id})
        
        if self.ws and not self.ws.closed:
            await self.ws.close()
        
        if self.client_session and not self.client_session.closed:
            await self.client_session.close()

        self.session_id = None
        self.connected = False
        self.client_session = None
        self.ws = None
        self.button_states.clear()
        self.fader_states.clear()
        


    async def __task_wrapper(self, callable: Callable):
        try:
            while True:
                await callable()
        except asyncio.CancelledError:
            pass


    async def __keep_alive(self):
        await asyncio.sleep(self.keep_alive_interval)
        if self.connected and self.ws and not self.ws.closed:
            try:
                await self.send({"session": self.session_id})
            except Exception as e:
                print(f"Keep-alive error: {e}")
                print("Attempting to reconnect...")
                self.connected = False
                await self.__connect()
        


    async def __process_messages(self):
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
                        self.connected = True
                        await self.__request_playbacks()
                    else:
                        print("Login failed")
                        break

                if data.get("responseType") == "playbacks":
                    await self.__process_playback(data)
                    await self.__request_playbacks()
                
                if data.get("session"):
                    self.session_id = data.get("session")
                
                if data.get("forceLogin") == True:
                    await self.__login()
                
                if data.get("status") and data.get("appType"):
                    await self.send({"session": 0})

        except Exception as e:
            print(f"Error in process_messages: {e}")
        finally:
            self.connected = False


    async def __process_playback(self, data):
        if "itemGroups" not in data:
            return

        def extract_executors(item_groups):
            for group in item_groups:
                executor_type = group.get("itemsType")
                if executor_type not in (ExecutorType.BUTTON, ExecutorType.FADER):
                    continue
                for item in (item for item_list in group.get("items", []) for item in item_list):
                    executor = {
                        "id": item.get("iExec"),
                        "is_active": (item.get("isRun", 0) == 1),
                        "position": 0
                    }
                    if executor_type == ExecutorType.FADER:
                        executor["position"] = get_fader_position(item)
                    yield executor_type, executor 

        def state_changed(state_dict, executor, keys):
            old_state = state_dict.get(executor["id"], {})
            new_state = {"position": executor["position"], "is_active": executor["is_active"]}
            changed = old_state != new_state
            if changed:
                state_dict[executor["id"]] = new_state
            return changed
        
        def get_fader_position(item):
            position = 0
            for block in item.get("executorBlocks", []):
                if "fader" in block:
                    position = block["fader"].get("v", 0)
                    break
            return position

        for executor_type, executor in extract_executors(data["itemGroups"]):
            if executor_type == ExecutorType.FADER: 
                if state_changed(self.fader_states, executor, ["position", "is_active"]):
                    for listener in self.fader_event_listeners:
                        listener(executor["id"] + 1, executor["is_active"], executor["position"])
                       
            else:  
                if state_changed(self.button_states, executor, ["is_active"]):
                    for listener in self.button_event_listeners:
                        listener(executor["id"] + 1, executor["is_active"])
        

    async def send(self, payload: Dict[str, Any]):
        try:
            if not self.ws:
                raise RuntimeError("WebSocket connection not established")
            await self.ws.send_str(json.dumps(payload, separators=(',', ':')))
        except Exception as e:
            print(f"Send error: {e}")


    async def __request_playbacks(self):
        if not self.session_id:
            return
        payload = {
            "requestType": "playbacks",
            "startIndex": self.executor_config.get("startIndex", []),
            "itemsCount": self.executor_config.get("itemsCount", []),
            "pageIndex": 0,     
            "itemsType": self.executor_config.get("itemsType", []),
            "view": 2,                  # fader view
            "execButtonViewMode": 1,    
            "buttonsViewMode": 0,
            "session": self.session_id,
            "maxRequests": 1
        }
        await self.send(payload)

    async def send_command(self, command: str):
        await self.send({
            "requestType": "command",
            "command": command,
            "session": self.session_id
        })


    async def set_fader(self, executor_number: int, normalized_position: float):
        if not self.connected: raise ConnectionError("Not connected to a Dot2 instance")
        if executor_number < 1: raise ValueError("Executor must be positive")
        command = f"Executor {executor_number} At {normalized_position * 100}"
        await self.send_command(command)
        

    async def set_button(self, executor_number: int, is_active: bool):
        if not self.connected: raise ConnectionError("Not connected to a Dot2 instance")
        if executor_number < 1: raise ValueError("Executor must be positive")
        command = f"Executor {executor_number} At {100 if is_active else 0}"
        await self.send_command(command)


    def add_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.append(callback)


    def add_button_event_listener(self, callback: Callable):
        self.button_event_listeners.append(callback)


    def remove_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.remove(callback)
    

    def remove_button_event_listener(self, callback: Callable):
        self.button_event_listeners.remove(callback)


    def set_executor_groups(self, configs: List[ExecutorGroup]):
        self.executor_config = {
            "startIndex": [],
            "itemsCount": [],
            "itemsType": []
        }
        for config in configs:
            self.executor_config["startIndex"].append(config.start_index - 1)
            self.executor_config["itemsCount"].append(config.count)
            self.executor_config["itemsType"].append(config.executor_type)

