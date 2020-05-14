from abc import ABC, abstractmethod

class PyMonitorCom(ABC):
    @abstractmethod
    def read(self):
        pass

    @abstractmethod
    def send(self):
        pass

    @abstractmethod
    def is_open(self):
        pass

    @abstractmethod
    def disconnect(self):
        pass

