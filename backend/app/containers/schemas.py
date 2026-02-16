from pydantic import BaseModel
from typing import Optional


class ContainerInfo(BaseModel):
    name: str
    id: str
    image: str
    status: str  # running, exited, paused, etc.
    state: str
    created: str
    ports: dict = {}
    labels: dict = {}
    cpu_percent: Optional[float] = None
    memory_usage: Optional[str] = None
    memory_limit: Optional[str] = None


class ContainerAction(BaseModel):
    action: str  # start, stop, restart, kill


class ContainerLogs(BaseModel):
    container_name: str
    logs: str
    lines: int
