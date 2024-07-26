import asyncio
import aiohttp
import json
from typing import Optional, Dict, Any, Callable, List
from ConnectionHandler import ConnectionHandler
from MsgHandler import MsgHandler
from Dot2Controller import Dot2Controller



def fader_changed(executor_number: int, normalized_position: float, is_active: bool):
    print(f"Executor {executor_number}: position {normalized_position}, active: {is_active}")



async def main():
    controller = Dot2Controller()
    
    controller.add_fader_event_listener(fader_changed)
    await controller.connect("127.0.0.1", "test", 0.08)

    print("Connected. Setting fader...")
    await controller.set_fader(21, 0.5)
    print("Fader set.")
    
    # keep running to recieve messages
    try:
        await asyncio.sleep(60)
    finally:
        await controller.disconnect()

if __name__ == "__main__":
    asyncio.run(main())