import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, Callable, List




class MsgHandler:
    def __init__(self):
        self.event_listeners = []



    async def proccess_messages(self, messages, is_connected) -> list:
        if not is_connected:
            raise RuntimeError("WebSocket connection not established")     

        try:
            async for message in messages:
                if message.type == aiohttp.WSMsgType.TEXT:
                    data = json.loads(message.data)
                    if "responseType" in data:
                        if data["responseType"] == "playbacks":
                            return self._destructure_playbacks(data)
                elif message.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                    break
        except Exception as e:
            raise Exception(e)



    def _destructure_playbacks(self, data):
        if "itemGroups" not in data:
            return
        executors = []
        for group in data["itemGroups"]:
            for item_list in group.get("items", []):
                for item in item_list:
                    executor = self._process_item(item)
                    if executor: 
                        executors.append(executor)
        return executors



    def _process_item(self, item) -> tuple[int, int, bool]:
        executor_id = item.get("iExec")
        executor_is_active = item.get("isRun", False)
        fader_value = self._get_fader_value(item)
    
        if executor_id is None:
            return
        if fader_value is None:
            return
        executor_id += 1 # sync id with named id
        normalized_position = float(fader_value)

        executor = [executor_id, normalized_position, executor_is_active]

        return executor




    def _get_fader_value(self, item):
        if 'executorBlocks' not in item:
            return None

        for block in item['executorBlocks']:
            if 'fader' in block:
                return block['fader'].get('v')
        
        return None


    def build_request_payload(self, session_id):
        if not session_id:
            return None
        payload = {
            "requestType": "playbacks",
            "startIndex": [0],
            "itemsCount": [8],
            "pageIndex": 0,
            "itemsType": [2],
            "view": 2,
            "execButtonViewMode": 1,
            "buttonsViewMode": 0,
            "session": session_id,
            "maxRequests": 1
        }
        return payload
