import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, Callable, List
from ConnectionHandler import ConnectionHandler
from MsgHandler import MsgHandler



class Dot2Controller:
    def __init__(self):
        self.connection = ConnectionHandler()
        self.msg_handler = MsgHandler()
        self.address: Optional[str] = None
        self.password: Optional[str] = None
        self.task_list = []
        self.fader_event_listeners: List[Callable] = []
        self.executor_states = {}

   
    async def connect(self, address: str, password: str, poll_delay: float):
        await self.connection.connect(address, password)
        self.task_list.append(asyncio.create_task(self._handle_listeners()))
        self.task_list.append(asyncio.create_task(self._poll_playback(poll_delay)))


    async def _handle_listeners(self):
        while True:
            executors = await self.msg_handler.proccess_messages(
                self.connection.get_messages(),
                self.connection.is_connected()
            ) 

            for executor in executors:
                executor_id, norm_pos, is_active = executor

                current_state = self.executor_states.get(executor_id, {})
                position_changed = abs(current_state.get('position', 0) - norm_pos) > 0.001
                active_changed = current_state.get('active', False) != is_active

                if not position_changed and not active_changed:
                    continue

                self.executor_states[executor_id] = {
                    'position': norm_pos,
                    'active': is_active
                }
                
                for listener in self.fader_event_listeners:
                    listener(executor_id, norm_pos, is_active)


    async def disconnect(self):
        for task in self.task_list:
            if task: task.cancel()
        await self.connection.disconnect()


    async def send_command(self, command: str):
        if not self.connection.is_connected():
            raise RuntimeError("Not initialized or logged in")
        await self.connection.send({
            "requestType": "command",
            "command": command,
            "session": self.connection.get_session_id()
        })


    async def set_fader(self, executor_number: int, normalized_position: float):
        if not self.connection.is_connected():
            raise RuntimeError("Not connected to dot2")
        command = f"Executor {executor_number} At {normalized_position * 100}"
        print(command)
        await self.send_command(command)


    def add_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.append(callback)


    def remove_fader_event_listener(self, callback: Callable):
        self.fader_event_listeners.remove(callback)

   
    async def _poll_playback(self, delay: float):
        while self.connection.is_connected():
            payload = self.msg_handler.build_request_payload(
                self.connection.get_session_id()
            )
            await self.connection.send(payload)
            await asyncio.sleep(delay) 