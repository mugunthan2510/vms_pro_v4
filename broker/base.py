from abc import ABC, abstractmethod

class BaseBroker(ABC):
    @abstractmethod
    async def connect(self): pass
