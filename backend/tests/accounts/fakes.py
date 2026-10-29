"""Small in-memory PyMongo-shaped objects for isolated repository tests."""

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from bson import ObjectId


class FakeCollection:
    """Implement the MongoDB operations used by account repositories."""

    def __init__(self) -> None:
        self.documents: dict[ObjectId, dict[str, Any]] = {}

    def insert_one(self, document: dict[str, Any]) -> SimpleNamespace:
        stored = deepcopy(document)
        inserted_id = stored.setdefault("_id", ObjectId())
        self.documents[inserted_id] = stored
        return SimpleNamespace(inserted_id=inserted_id)

    def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        for document in self.documents.values():
            if all(document.get(key) == value for key, value in query.items()):
                return deepcopy(document)
        return None

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
    ) -> SimpleNamespace:
        for document in self.documents.values():
            if all(document.get(key) == value for key, value in query.items()):
                self._apply(document, update)
                return SimpleNamespace(matched_count=1)
        return SimpleNamespace(matched_count=0)

    def update_many(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
    ) -> SimpleNamespace:
        matched_count = 0
        for document in self.documents.values():
            if all(document.get(key) == value for key, value in query.items()):
                self._apply(document, update)
                matched_count += 1
        return SimpleNamespace(matched_count=matched_count)

    def delete_one(self, query: dict[str, Any]) -> SimpleNamespace:
        for document_id, document in self.documents.items():
            if all(document.get(key) == value for key, value in query.items()):
                del self.documents[document_id]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    @staticmethod
    def _apply(document: dict[str, Any], update: dict[str, Any]) -> None:
        for key, values in update.get("$set", {}).items():
            document[key] = deepcopy(values)
        for key, amount in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + amount


class FakeDatabase:
    """Return one isolated fake collection per MongoDB collection name."""

    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, collection_name: str) -> FakeCollection:
        return self.collections.setdefault(collection_name, FakeCollection())
