import asyncio
import aiohttp
from pmpcontrol import PMPController, PMPEvent
from typing import Optional, Dict, Any, Callable, List
from ConnectionHandler import ConnectionHandler
from MsgHandler import MsgHandler
from Dot2Controller import Dot2Controller
MAX_14BIT = 16383
def handle_fader(self, fader_number: int, value: int):
    if 0 <= fader_number < 9:
        print(f"FN: {fader_number}")
        normalized_value = value / MAX_14BIT
        if self.sync_faders:
            self.set_fader(fader_number, normalized_value)
        for callback in self.event_callbacks[PMPEvent.FADER]:
            callback(fader_number, normalized_value)


dot2 = Dot2Controller()
platformM = PMPController(True)


def dot2_fader_changed(executor_number: int, normalized_position: float, is_active: bool):
    mapped_num = 9 - executor_number 
    print(f"SETTING PLATFORM({mapped_num}, {normalized_position: .3f})")
    platformM.set_fader(mapped_num, normalized_position)
    # d 1-8 = p 8-1

def pmp_platform_changed(fader_numer: int, normalized_value: float):
    print("update")
    mapped_num = 9 - fader_numer
    print(f"SETTING DOT2({mapped_num}, {normalized_value: .3f} )")
    asyncio.create_task(dot2.set_fader(mapped_num, normalized_value))
    # platformM.set_fader(fader_numer, normalized_value)


async def main():

    dot2.add_fader_event_listener(dot2_fader_changed)
    platformM.add_event_listener(PMPEvent.FADER, pmp_platform_changed)

    platformM.connect()
    await dot2.connect("127.0.0.1", "password", 0.08)
    
    
    try:
        while True:
            await asyncio.sleep(1)
            
    finally:
        await dot2.disconnect()
        platformM.reset()
        platformM.disconnect()

if __name__ == "__main__":
    asyncio.run(main())