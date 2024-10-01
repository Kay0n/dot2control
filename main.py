import asyncio
import aiohttp
import sys
from pmpcontroller import PMPController, PMPEvent
from Dot2Controller import Dot2Controller, ExecutorType, ExecutorGroup

dot2 = Dot2Controller()
platform_m = PMPController()
dot2_fader_queue = asyncio.Queue()

dot2.set_executor_groups([
    ExecutorGroup(1, 8, ExecutorType.FADER),
    # ExecutorGroup(101, 8, ExecutorType.BUTTON),
    # ExecutorGroup(201, 8, ExecutorType.BUTTON)
])



def dot2_fader_changed(executor_number: int, is_active: bool, normalized_value: float):
    if not platform_m.is_connected(): return
    mapped_num = 8 - executor_number
    print(f"SETTING PLATFORM FADER({mapped_num}, {normalized_value:.3f})")
    platform_m.set_fader(mapped_num, normalized_value)
    platform_m.set_button(mapped_num + 8, is_active)
        
# def dot2_button_changed(executor_number: int, is_active: bool):
#     mapped_num = 8 - executor_number
#     print(f"SETTING PLATFORM BUTTON({mapped_num}, {is_active})")
#     platformM.set_button(mapped_num + 8, is_active) # FIXME button mapping



def pmp_fader_changed(fader_number: int, normalized_value: float):
    if not dot2.is_connected(): return
    mapped_num = 8 - fader_number
    if(mapped_num < 1):
        return
    print(f"QUEUEING DOT2 FADER({mapped_num}, {normalized_value:.3f})")
    dot2_fader_queue.put_nowait([ExecutorType.FADER, mapped_num, normalized_value])

    # platformM.set_fader(fader_number, normalized_value)

# def pmp_button_changed(button_number: int, is_pressed: bool, button_state: bool): # FIXME all
#     mapped_num = 8 - button_number
#     print(f"SETTING DOT2 BUTTON({mapped_num}, {is_active})")
#     dot2Queue.put_nowait([ExecutorType.BUTTON, mapped_num, is_active])
#     platformM.set_button(button_number, is_active)



def connect_to_pmp() -> bool :
    try:
        platform_m.connect()
    except OSError:
        return False
    return True



async def connect_to_dot2() -> bool:
    try:
        await dot2.connect("127.0.0.1", "password")
    except OSError as e:
        return False
    return True



async def update_dot2():
    while not dot2_fader_queue.empty():
        executor_type, executor_number, normalized_value = await dot2_fader_queue.get()
        if executor_type == ExecutorType.FADER:
            print(f"SETTING DOT2 FADER({executor_number}, {normalized_value:.3f})")
            await dot2.set_fader(executor_number, normalized_value)
        elif executor_type == ExecutorType.BUTTON:
            pass


dot2.add_fader_event_listener(dot2_fader_changed)
platform_m.add_event_listener(PMPEvent.FADER, pmp_fader_changed)



async def main(): 
    async def try_connect():
        while True:
            await disconnect_all()
            if not connect_to_pmp():
                print("Could not connect to pmp, waiting 10s...")
                await asyncio.sleep(5)
            elif not await connect_to_dot2():
                print("Could not connect to dot2, waiting 10s...")
                await asyncio.sleep(5)
            else:
                print("Connected, now syncing Dot2 to Platform M+")
                break

    async def disconnect_all():
        await dot2.disconnect()
        if platform_m.is_connected():
            platform_m.reset()      
        platform_m.disconnect()


    try:
        while True:
            await try_connect()
            try:
                while platform_m.is_connected() and dot2.is_connected():
                    await update_dot2()
                    await asyncio.sleep(0.005)

            except ConnectionAbortedError:
                pass


    finally:
        await disconnect_all()
        sys.exit()



if __name__ == "__main__":
    asyncio.run(main())
