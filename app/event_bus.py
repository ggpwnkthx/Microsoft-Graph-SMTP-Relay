import asyncio
import logging
from threading import Thread, RLock

class EventBus:
    def __init__(self):
        self.__events = {}          # event_name -> [handlers]
        self.__loop = None          # single long-lived loop
        self.__thread = None        # single long-lived thread
        self.__lock = RLock()

    def subscribe(self, event_name, handler):
        with self.__lock:
            self.__events.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name, handler):
        with self.__lock:
            if event_name in self.__events and handler in self.__events[event_name]:
                self.__events[event_name].remove(handler)

    def __background_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def __ensure_loop(self):
        if self.__loop is None or self.__loop.is_closed():
            loop = asyncio.new_event_loop()
            t = Thread(target=self.__background_loop, args=(loop,), daemon=True)
            t.start()
            self.__loop = loop
            self.__thread = t

    def publishSync(self, event_name, *args) -> bool:
        # Reuse the single loop/thread; do NOT create a new one per call.
        self.__ensure_loop()
        fut = asyncio.run_coroutine_threadsafe(
            self.publish(event_name, *args),   # <-- expand args correctly
            self.__loop
        )
        return fut.result()

    async def publish(self, event_name, *args) -> bool:
        result = False
        # snapshot handlers to avoid mutation during iteration
        handlers = list(self.__events.get(event_name, []))
        if handlers:
            logging.debug(f"Publishing event: {event_name}")
            for handler in handlers:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(*args)
                else:
                    result = handler(*args)
        return result

    # (optional) call this on clean shutdown if you wire signals
    def shutdown(self, timeout=1.0):
        if self.__loop and self.__loop.is_running():
            self.__loop.call_soon_threadsafe(self.__loop.stop)
            if self.__thread:
                self.__thread.join(timeout=timeout)

event_bus_instance = EventBus()
