from dataclasses import dataclass


@dataclass
class ServerConfig:
    host: str
    port: int

    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError(f"port out of range: {self.port}")
