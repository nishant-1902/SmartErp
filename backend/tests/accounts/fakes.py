"""Small in-memory PyMongo-shaped objects for isolated repository tests."""

from copy import deepcopy
import re
from types import SimpleNamespace
from typing import Any, Iterable, Iterator

from bson import ObjectId


class FakeCollection:
    """Implement the MongoDB operations used by account repositories."""

    def __init__(self) -> None:
        self.documents: dict[Any, dict[str, Any]] = {}

    def insert_one(self, document: dict[str, Any], **kwargs: Any) -> SimpleNamespace:
        stored = deepcopy(document)
        inserted_id = stored.setdefault("_id", ObjectId())
        self.documents[inserted_id] = stored
        return SimpleNamespace(inserted_id=inserted_id)

    def find_one(
        self,
        query: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        for document in self.documents.values():
            if self._matches(document, query):
                return deepcopy(document)
        return None

    def find(self, query: dict[str, Any], **kwargs: Any) -> "FakeCursor":
        return FakeCursor(
            deepcopy(document)
            for document in self.documents.values()
            if self._matches(document, query)
        )

    def count_documents(self, query: dict[str, Any], **kwargs: Any) -> int:
        return sum(
            self._matches(document, query)
            for document in self.documents.values()
        )

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        **kwargs: Any,
    ) -> SimpleNamespace:
        for document in self.documents.values():
            if self._matches(document, query):
                self._apply(document, update)
                return SimpleNamespace(matched_count=1)
        if upsert:
            document = {
                key: value
                for key, value in query.items()
                if not key.startswith("$") and not isinstance(value, dict)
            }
            self._apply(document, update)
            self.insert_one(document)
            return SimpleNamespace(matched_count=0, upserted_id=document["_id"])
        return SimpleNamespace(matched_count=0)

    def update_many(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        **kwargs: Any,
    ) -> SimpleNamespace:
        matched_count = 0
        for document in self.documents.values():
            if self._matches(document, query):
                self._apply(document, update)
                matched_count += 1
        return SimpleNamespace(matched_count=matched_count)

    def delete_one(self, query: dict[str, Any]) -> SimpleNamespace:
        for document_id, document in self.documents.items():
            if self._matches(document, query):
                del self.documents[document_id]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    @staticmethod
    def _apply(document: dict[str, Any], update: dict[str, Any]) -> None:
        for key, values in update.get("$set", {}).items():
            document[key] = deepcopy(values)
        for key, amount in update.get("$inc", {}).items():
            document[key] = document.get(key, 0) + amount

    @classmethod
    def _matches(cls, document: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(document, clause) for clause in expected):
                    return False
                continue
            actual = document.get(key)
            if isinstance(expected, dict):
                for operator, value in expected.items():
                    if operator == "$regex":
                        flags = re.IGNORECASE if expected.get("$options") == "i" else 0
                        if actual is None or re.search(value, actual, flags) is None:
                            return False
                    elif operator == "$options":
                        continue
                    elif operator == "$ne" and actual == value:
                        return False
                    elif operator == "$gte" and (actual is None or actual < value):
                        return False
                    elif operator == "$lte" and (actual is None or actual > value):
                        return False
                continue
            if actual != expected:
                return False
        return True


class FakeCursor:
    """Provide the subset of PyMongo cursor operations used by list repositories."""

    def __init__(self, documents: Iterable[dict[str, Any]]) -> None:
        self.documents = list(documents)

    def sort(self, fields: list[tuple[str, int]]) -> "FakeCursor":
        for field, direction in reversed(fields):
            self.documents.sort(
                key=lambda document: (
                    document.get(field) is None,
                    document.get(field),
                ),
                reverse=direction < 0,
            )
        return self

    def skip(self, count: int) -> "FakeCursor":
        self.documents = self.documents[count:]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self.documents = self.documents[:count]
        return self

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.documents)


class FakeDatabase:
    """Return one isolated fake collection per MongoDB collection name."""

    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, collection_name: str) -> FakeCollection:
        return self.collections.setdefault(collection_name, FakeCollection())
