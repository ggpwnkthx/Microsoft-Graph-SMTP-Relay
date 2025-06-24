import asyncio
import logging
from threading import Thread


class EventBus:
    def __init__(self):
        # stores all event subscriptions
        self.__events = {}

    def subscribe(self, event_name, handler):
        if event_name not in self.__events:
            self.__events[event_name] = []
        self.__events[event_name].append(handler)

    def unsubscribe(self, event_name, handler):
        if event_name in self.__events and handler in self.__events[event_name]:
            self.__events[event_name].remove(handler)

    def __background_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def publishSync(self, event_name, *args) -> bool:
        loop = asyncio.new_event_loop()
        t = Thread(target=self.__background_loop, args=(loop,), daemon=True)
        t.start()
        task = asyncio.run_coroutine_threadsafe(self.publish(event_name, args), loop)
        return task.result()

    async def publish(self, event_name, *args) -> bool:
        result = False
        if event_name in self.__events:
            logging.debug(f"Publishing event: {event_name}")
            for handler in self.__events[event_name]:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*args)
                else:
                    result = handler(*args)
        return result

event_bus_instance = EventBus()