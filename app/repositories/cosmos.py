from azure.cosmos import ContainerProxy, exceptions

from app.models import URLRecord


class CosmosRepository:
    def __init__(self, container: ContainerProxy) -> None:
        self._container = container

    def create_if_absent(self, record: URLRecord) -> bool:
        try:
            self._container.create_item(body=record.model_dump(mode="json"))
        except exceptions.CosmosResourceExistsError:
            return False
        return True

    def get_by_id(self, code: str) -> URLRecord | None:
        try:
            document = self._container.read_item(item=code, partition_key=code)
        except exceptions.CosmosResourceNotFoundError:
            return None
        return URLRecord.model_validate(document)
