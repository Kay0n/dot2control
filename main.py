import asyncio
import aiohttp
from pmpcontrol import PMPController, PMPEvent
from typing import Optional, Dict, Any, Callable, List
from ConnectionHandler import ConnectionHandler
from MsgHandler import MsgHandler
from Dot2Controller import Dot2Controller

dot2 = Dot2Controller()
platformM = PMPController(True)
queue = asyncio.Queue()



def dot2_fader_changed(executor_number: int, normalized_position: float, is_active: bool):
    mapped_num = 9 - executor_number
    print(f"SETTING PLATFORM({mapped_num}, {normalized_position:.3f})")
    platformM.set_fader(mapped_num, normalized_position)

def pmp_platform_changed(fader_number: int, normalized_value: float):
    mapped_num = 9 - fader_number
    print(f"SETTING DOT2({mapped_num}, {normalized_value:.3f})")
    queue.put_nowait([mapped_num, normalized_value])



async def main():



    dot2.add_fader_event_listener(dot2_fader_changed)
    platformM.add_event_listener(PMPEvent.FADER, pmp_platform_changed)

    platformM.connect()
    await dot2.connect("127.0.0.1", "password", 0.08)

    
    try:
        while True:
            await asyncio.sleep(0.1)
            await dot2.set_fader(1, 0.5)
            # while not queue.empty():
            #     mapped_num, normalized_value = await queue.get()
            #     await dot2.set_fader(mapped_num, normalized_value)
    finally:
        await dot2.disconnect()
        platformM.reset()
        platformM.disconnect()
        print("disconnected")

if __name__ == "__main__":
    asyncio.run(main())