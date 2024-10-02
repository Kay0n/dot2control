import asyncio
from pmpcontroller import PMPController, PMPEvent
from Dot2Controller import Dot2Controller, ExecutorType, ExecutorGroup



class Dot2PMPSync:
    def __init__(self):
        self.dot2 = Dot2Controller()
        self.platform_m = PMPController()
        self.dot2_fader_queue = asyncio.Queue()
        self.dot2_button_queue = asyncio.Queue()

        self.dot2.set_executor_groups([
            ExecutorGroup(1, 8, ExecutorType.FADER),
            ExecutorGroup(101, 8, ExecutorType.BUTTON),
            ExecutorGroup(201, 8, ExecutorType.BUTTON)
        ])

        self.dot2.add_fader_event_listener(self.dot2_fader_changed)
        self.dot2.add_button_event_listener(self.dot2_button_changed)
        self.platform_m.add_event_listener(PMPEvent.FADER, self.pmp_fader_changed)
        self.platform_m.add_event_listener(PMPEvent.BUTTON, self.pmp_button_changed)


    def map_dot2_btn_to_pmp(self, button_num):
        if 101 <= button_num <= 108:
            return 24 + (108 - button_num)
        elif 201 <= button_num <= 208:
            return 16 + (208 - button_num)
        raise ValueError("Button number must be in the range 101-108 or 201-208")


    def map_pmp_btn_to_dot2(self, button_num):
        if 24 <= button_num <= 31:
            return 108 - (button_num - 24)
        elif 16 <= button_num <= 23:
            return 208 - (button_num - 16)
        raise ValueError("Button number must be in the range 16-31")


    def dot2_fader_changed(self, executor_number: int, is_active: bool, normalized_value: float):
        if not self.platform_m.is_connected(): return
        mapped_num = 8 - executor_number
        self.platform_m.set_fader(mapped_num, normalized_value)
        self.platform_m.set_button(mapped_num + 8, is_active)  # SOLO button lights green when fader > 0


    def dot2_button_changed(self, executor_number: int, is_active: bool):
        if not self.platform_m.is_connected(): return
        try:
            mapped_num = self.map_dot2_btn_to_pmp(executor_number)
        except ValueError: return
        self.platform_m.set_button(mapped_num, is_active)


    def pmp_fader_changed(self, fader_number: int, normalized_value: float):
        if not self.dot2.is_connected(): return
        mapped_num = 8 - fader_number
        if mapped_num >= 1:
            self.dot2_fader_queue.put_nowait([mapped_num, normalized_value])


    def pmp_button_changed(self, button_number: int, is_pressed: bool, button_state: bool):
        if not self.dot2.is_connected() or not is_pressed: return
        try:
            mapped_num = self.map_pmp_btn_to_dot2(button_number)
        except ValueError: return
        self.dot2_button_queue.put_nowait([mapped_num, not button_state])


    async def connect_to_pmp(self):
        try:
            self.platform_m.connect()
            return True
        except OSError:
            return False


    async def connect_to_dot2(self):
        try:
            await self.dot2.connect("127.0.0.1", "password")
            return True
        except OSError:
            return False


    async def update_dot2(self):
        while not self.dot2_fader_queue.empty():
            executor_number, normalized_value = await self.dot2_fader_queue.get()
            await self.dot2.set_fader(executor_number, normalized_value)
        while not self.dot2_button_queue.empty():
            executor_number, new_state = await self.dot2_button_queue.get()
            await self.dot2.set_button(executor_number, new_state)


    async def try_connect(self):
        while True:
            if not await self.connect_to_pmp(): name = "pmp"
            elif not await self.connect_to_dot2(): name = "dot2"
            else:
                print("Connected, now syncing Dot2 to Platform M+")
                self.platform_m.set_button(86,True) # blue indicator light to show sync
                return
            print(f"Could not connect to {name}, waiting 10s...")
            await self.disconnect_all()
            await asyncio.sleep(10)


    async def disconnect_all(self):
        await self.dot2.disconnect()
        if self.platform_m.is_connected():
            self.platform_m.reset()
        self.platform_m.disconnect()


    async def run(self):
        try:
            while True:
                await self.try_connect()
                try:
                    while self.platform_m.is_connected() and self.dot2.is_connected():
                        await self.update_dot2()
                        await asyncio.sleep(0.005)
                except ConnectionAbortedError:
                    pass
        finally:
            await self.disconnect_all()
            exit()



if __name__ == "__main__":
    sync = Dot2PMPSync()
    asyncio.run(sync.run())
