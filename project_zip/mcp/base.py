from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseMCP(ABC):
    """Interface every domain server must implement."""

    domain: str  # short lowercase key, e.g. "github"

    @abstractmethod
    def capabilities(self) -> str:
        """Single‑line human description used in help message."""
        ...

    @abstractmethod
    def execute(self, action: str, params: Dict[str, Any]) -> str:
        """Run the requested action with supplied params."""
        ...
