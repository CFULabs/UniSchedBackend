from abc import ABC, abstractmethod
from .types import Schedule, Group
from aiohttp import ClientSession


class ScheduleProvider(ABC):
    @property
    @abstractmethod
    def description(self) -> str:
        """Human readable description"""

    async def on_network_fetch(self, session: ClientSession):
        """Called when the provider should fetch its data from network"""

    @property
    @abstractmethod
    def groups(self) -> list[Group]:
        """Available groups"""

    @abstractmethod
    async def get_schedule(self, group_id: str | int) -> Schedule:
        """Main method, must return a Schedule object"""
