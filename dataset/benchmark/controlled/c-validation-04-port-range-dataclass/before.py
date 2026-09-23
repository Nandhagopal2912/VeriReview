from dataclasses import dataclass


@dataclass
class ServerConfig:
    host: str
    port: int
