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
    repository_backend: Literal["memory", "cosmos", "dynamodb"] = "memory"
    cosmos_endpoint: str = ""
    cosmos_database: str = ""
    cosmos_container: str = ""
    aws_region: str = ""
    dynamodb_table: str = ""

    def __post_init__(self) -> None:
        if self.repository_backend not in ("memory", "cosmos", "dynamodb"):
            raise ValueError("REPOSITORY_BACKEND must be memory, cosmos or dynamodb")
        if self.repository_backend == "cosmos":
            missing = [name for name, value in (("COSMOS_ENDPOINT", self.cosmos_endpoint),
                       ("COSMOS_DATABASE", self.cosmos_database),
                       ("COSMOS_CONTAINER", self.cosmos_container)) if not value.strip()]
            if missing:
                raise ValueError("Missing Cosmos configuration: " + ", ".join(missing))
        if self.repository_backend == "dynamodb":
            missing = [name for name, value in (("AWS_REGION", self.aws_region),
                       ("DYNAMODB_TABLE", self.dynamodb_table)) if not value.strip()]
            if missing:
                raise ValueError("Missing DynamoDB configuration: " + ", ".join(missing))

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
        return cls(cloud=cast(Cloud, cloud), writer_mode=cast(WriterMode, mode), writer_epoch=epoch,
                   repository_backend=cast(Literal["memory", "cosmos", "dynamodb"], os.getenv("REPOSITORY_BACKEND", "memory")),
                   cosmos_endpoint=os.getenv("COSMOS_ENDPOINT", ""),
                   cosmos_database=os.getenv("COSMOS_DATABASE", ""),
                   cosmos_container=os.getenv("COSMOS_CONTAINER", ""),
                   aws_region=os.getenv("AWS_REGION", ""),
                   dynamodb_table=os.getenv("DYNAMODB_TABLE", ""))
