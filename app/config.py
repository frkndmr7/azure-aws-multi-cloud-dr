import os
from dataclasses import dataclass
from typing import Literal, cast

Cloud = Literal["azure", "aws"]
WriterMode = Literal["active", "standby", "frozen"]


@dataclass(frozen=True)
class Settings:
    cloud: Cloud = "azure"
    writer_mode: WriterMode = "active"
    writer_epoch: int = 1

    @classmethod
    def from_env(cls) -> "Settings":
        cloud = os.getenv("CLOUD_ROLE", "azure")
        mode = os.getenv("WRITER_MODE", "active")
        if cloud not in ("azure", "aws"):
            raise ValueError("CLOUD_ROLE must be azure or aws")
        if mode not in ("active", "standby", "frozen"):
            raise ValueError("WRITER_MODE must be active, standby or frozen")
        epoch = int(os.getenv("WRITER_EPOCH", "1"))
        if epoch < 0:
            raise ValueError("WRITER_EPOCH must be non-negative")
        return cls(cast(Cloud, cloud), cast(WriterMode, mode), epoch)
