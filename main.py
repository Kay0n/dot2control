import asyncio
import aiohttp
from pmpcontrol import PMPController, PMPEvent
from Dot2Controller import Dot2Controller, ExecutorType, ExecutorGroup

dot2 = Dot2Controller()
platformM = PMPController()
dot2Queue = asyncio.Queue()


dot2.set_executor_groups([
    ExecutorGroup(1, 8, ExecutorType.FADER),
    ExecutorGroup(101, 8, ExecutorType.BUTTON),
    ExecutorGroup(201, 8, ExecutorType.BUTTON)
])


def dot2_fader_changed(executor_number: int, is_active: bool, normalized_value: float):
    mapped_num = 8 - executor_number
    print(f"SETTING PLATFORM FADER({mapped_num}, {normalized_value:.3f})")
    platformM.set_fader(mapped_num, normalized_value)
    platformM.set_button(mapped_num + 8, is_active)
        
def dot2_button_changed(executor_number: int, is_active: bool):
    mapped_num = 8 - executor_number
    print(f"SETTING PLATFORM BUTTON({mapped_num}, {is_active})")
    platformM.set_button(mapped_num + 8, is_active) # FIXME button mapping

def pmp_fader_changed(fader_number: int, normalized_value: float):
    mapped_num = 8 - fader_number
    print(f"SETTING DOT2 FADER({mapped_num}, {normalized_value:.3f})")
    dot2Queue.put_nowait([ExecutorType.FADER, mapped_num, normalized_value])
    platformM.set_fader(fader_number, normalized_value)


def pmp_button_changed(button_number: int, is_pressed: bool, button_state: bool): # FIXME all
    mapped_num = 8 - button_number
    print(f"SETTING DOT2 BUTTON({mapped_num}, {is_active})")
    dot2Queue.put_nowait([ExecutorType.BUTTON, mapped_num, is_active])
    platformM.set_button(button_number, is_active)



async def main():

    dot2.add_fader_event_listener(dot2_fader_changed)
    dot2.add_button_event_listener(dot2_button_changed)
    platformM.add_event_listener(PMPEvent.FADER, pmp_button_changed)

    platformM.connect()
    await dot2.connect("127.0.0.1", "test", 0.08)

    try:
        while True:
            await asyncio.sleep(0.1)
            
            while not dot2Queue.empty():
                mapped_num, normalized_value = await dot2Queue.get()
                print(f"SETTING DOT2({mapped_num}, {normalized_value:.3f})")
                await dot2.set_fader(mapped_num, normalized_value)
    finally:
        await dot2.disconnect()
        platformM.reset()
        platformM.disconnect()
        print("disconnected")



async def test():
    dot2.add_fader_event_listener(dot2_fader_changed)
    dot2.add_button_event_listener(dot2_button_changed)
    try:
        await dot2.connect("127.0.0.1", "test")
        while True:
            await asyncio.sleep(2)
            await dot2.set_fader(1, 1)
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        await dot2.disconnect()



if __name__ == "__main__":
    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("Keyboard interrupt received, exiting...")