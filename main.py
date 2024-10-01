import asyncio
import aiohttp
from pmpcontroller import PMPController, PMPEvent
from Dot2Controller import Dot2Controller, ExecutorType, ExecutorGroup

dot2 = Dot2Controller()
platformM = PMPController()
dot2Queue = asyncio.Queue()

dot2.set_executor_groups([
    ExecutorGroup(1, 8, ExecutorType.FADER),
    # ExecutorGroup(101, 8, ExecutorType.BUTTON),
    # ExecutorGroup(201, 8, ExecutorType.BUTTON)
])



def dot2_fader_changed(executor_number: int, is_active: bool, normalized_value: float):
    mapped_num = 8 - executor_number
    print(f"SETTING PLATFORM FADER({mapped_num}, {normalized_value:.3f})")
    platformM.set_fader(mapped_num, normalized_value)
    platformM.set_button(mapped_num + 8, is_active)
        
# def dot2_button_changed(executor_number: int, is_active: bool):
#     mapped_num = 8 - executor_number
#     print(f"SETTING PLATFORM BUTTON({mapped_num}, {is_active})")
#     platformM.set_button(mapped_num + 8, is_active) # FIXME button mapping



def pmp_fader_changed(fader_number: int, normalized_value: float):

    mapped_num = 8 - fader_number
    if(mapped_num < 1):
        return
    print(f"SETTING DOT2 FADER({mapped_num}, {normalized_value:.3f})")
    print("add to queue")
    dot2Queue.put_nowait([ExecutorType.FADER, mapped_num, normalized_value])
    print("set fader")
    # platformM.set_fader(fader_number, normalized_value)

# def pmp_button_changed(button_number: int, is_pressed: bool, button_state: bool): # FIXME all
#     mapped_num = 8 - button_number
#     print(f"SETTING DOT2 BUTTON({mapped_num}, {is_active})")
#     dot2Queue.put_nowait([ExecutorType.BUTTON, mapped_num, is_active])
#     platformM.set_button(button_number, is_active)



def connect_to_pmp() -> bool :
    try:
        platformM.connect()
    except OSError:
        return False
    return True



async def connect_to_dot2() -> bool:
    try:
        await dot2.connect("127.0.0.1", "password")
    except OSError:
        return False
    return True



async def update_dot2():
    while not dot2Queue.empty():
        executor_type, executor_number, normalized_value = await dot2Queue.get()
        if executor_type == ExecutorType.FADER:
            await dot2.set_fader(executor_number, normalized_value)
        elif executor_type == ExecutorType.BUTTON:
            pass



async def main(): 
    async def try_connect():
        while not await connect_to_pmp() or not await connect_to_dot2():
            print("Could not connect, waiting 5s...")
            await asyncio.sleep(5)
        return True

    async def handle_disconnection():
        await dot2.disconnect()
        if platformM.is_connected():
            platformM.reset()  
        platformM.disconnect()

    try:
        while True:
            await try_connect()

            try:
                while platformM.is_connected() and dot2.is_connected():
                    update_dot2()
                    await asyncio.sleep(0.1)

            except ConnectionAbortedError:
                await handle_disconnection()

    finally:
        await handle_disconnection()



if __name__ == "__main__":
    asyncio.run(main())