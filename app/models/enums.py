from enum import Enum


class MonitorMethod(str, Enum):
    GET = "GET"
    HEAD = "HEAD"


class MonitorStatus(str, Enum):
    active = "active"
    paused = "paused"


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"
    dead = "dead"


class AlertType(str, Enum):
    down = "down"
    recovery = "recovery"

