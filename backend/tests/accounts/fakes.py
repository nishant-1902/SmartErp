"""Small in-memory PyMongo-shaped objects for isolated repository tests."""

from copy import deepcopy
import re
from types import SimpleNamespace
from threading import RLock
from typing import Any, Iterable, Iterator

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


class FakeCollection:
    """Implement the MongoDB operations used by account repositories."""

    def __init__(self, unique_fields: tuple[tuple[str, ...], ...] = ()) -> None:
        self.documents: dict[Any, dict[str, Any]] = {}
        self.unique_fields = unique_fields
        self.lock = RLock()

    def insert_one(self, document: dict[str, Any], **kwargs: Any) -> SimpleNamespace:
        with self.lock:
            stored = deepcopy(document)
            for fields in self.unique_fields:
                values = tuple(stored.get(field) for field in fields)
                if any(
                    tuple(existing.get(field) for field in fields) == values
                    for existing in self.documents.values()
                ):
                    raise DuplicateKeyError(
                        f"Duplicate fake unique key for fields {fields!r}."
                    )
            inserted_id = stored.setdefault("_id", ObjectId())
            self.documents[inserted_id] = stored
            return SimpleNamespace(inserted_id=inserted_id)

    def find_one(
        self,
        query: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        with self.lock:
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
        with self.lock:
            return sum(
                self._matches(document, query)
                for document in self.documents.values()
            )

    def distinct(self, field: str, query: dict[str, Any] | None = None) -> list[Any]:
        """Return unique values for a field, optionally matching a query."""
        values = {
            document[field]
            for document in self.documents.values()
            if field in document and self._matches(document, query or {})
        }
        return list(values)

    def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        **kwargs: Any,
    ) -> SimpleNamespace:
        with self.lock:
            for document in self.documents.values():
                if self._matches(document, query):
                    self._apply(document, update, query)
                    return SimpleNamespace(matched_count=1, modified_count=1)
            if upsert:
                document = {
                    key: value
                    for key, value in query.items()
                    if not key.startswith("$") and not isinstance(value, dict)
                }
                self._apply(document, update)
                self.insert_one(document)
                return SimpleNamespace(matched_count=0, upserted_id=document["_id"])
            return SimpleNamespace(matched_count=0, modified_count=0)

    def find_one_and_update(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        *,
        return_document: ReturnDocument = ReturnDocument.BEFORE,
        upsert: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Atomically match, update, and return a fake document."""
        with self.lock:
            for document in self.documents.values():
                if self._matches(document, query):
                    before = deepcopy(document)
                    self._apply(document, update, query)
                    if return_document == ReturnDocument.AFTER:
                        return deepcopy(document)
                    return before
            if upsert:
                document = {
                    key: deepcopy(value)
                    for key, value in query.items()
                    if not key.startswith("$") and not isinstance(value, dict)
                }
                self._apply(document, update)
                self.insert_one(document)
                if return_document == ReturnDocument.AFTER:
                    return deepcopy(document)
                return None
            return None

    def update_many(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        **kwargs: Any,
    ) -> SimpleNamespace:
        matched_count = 0
        for document in self.documents.values():
            if self._matches(document, query):
                self._apply(document, update, query)
                matched_count += 1
        return SimpleNamespace(
            matched_count=matched_count,
            modified_count=matched_count,
        )

    def delete_one(self, query: dict[str, Any]) -> SimpleNamespace:
        for document_id, document in self.documents.items():
            if self._matches(document, query):
                del self.documents[document_id]
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    @staticmethod
    def _apply(
        document: dict[str, Any],
        update: dict[str, Any],
        query: dict[str, Any] | None = None,
    ) -> None:
        for key, values in update.get("$set", {}).items():
            document[key] = deepcopy(values)
        for key, amount in update.get("$inc", {}).items():
            if ".$." in key:
                array_name, nested_field = key.split(".$.", 1)
                array_query = (query or {}).get(array_name, {}).get("$elemMatch", {})
                for item in document.get(array_name, []):
                    if FakeCollection._matches(item, array_query):
                        item[nested_field] = item.get(nested_field, 0) + amount
                        break
            else:
                document[key] = document.get(key, 0) + amount
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(deepcopy(value))

    @classmethod
    def _matches(cls, document: dict[str, Any], query: dict[str, Any]) -> bool:
        for key, expected in query.items():
            if key == "$or":
                if not any(cls._matches(document, clause) for clause in expected):
                    return False
                continue
            if key == "$expr":
                operator, operands = next(iter(expected.items()))
                left, right = (
                    cls._expression_value(document, operand)
                    for operand in operands
                )
                if operator == "$lte" and not left <= right:
                    return False
                if operator == "$gte" and not left >= right:
                    return False
                if operator == "$gt" and not left > right:
                    return False
                continue
            actual = document.get(key)
            if isinstance(expected, dict):
                if "$elemMatch" in expected:
                    if not isinstance(actual, list) or not any(
                        cls._matches(item, expected["$elemMatch"])
                        for item in actual
                    ):
                        return False
                    continue
                for operator, value in expected.items():
                    if operator == "$regex":
                        flags = re.IGNORECASE if expected.get("$options") == "i" else 0
                        if actual is None or re.search(value, actual, flags) is None:
                            return False
                    elif operator == "$options":
                        continue
                    elif operator == "$in" and actual not in value:
                        return False
                    elif operator == "$ne" and actual == value:
                        return False
                    elif operator == "$gte" and (actual is None or actual < value):
                        return False
                    elif operator == "$lte" and (actual is None or actual > value):
                        return False
                    elif operator == "$elemMatch":
                        if not isinstance(actual, list) or not any(
                            cls._matches(item, value) for item in actual
                        ):
                            return False
                continue
            if actual != expected:
                return False
        return True

    @classmethod
    def _expression_value(cls, document: dict[str, Any], expression: Any) -> Any:
        if isinstance(expression, str) and expression.startswith("$"):
            return document.get(expression[1:])
        if isinstance(expression, dict) and "$subtract" in expression:
            left, right = (
                cls._expression_value(document, operand)
                for operand in expression["$subtract"]
            )
            return left - right
        return expression


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
        if collection_name not in self.collections:
            unique_fields = {
                "idempotency_keys": (("scope", "key"),),
                "purchase_orders": (("po_number",),),
                "sales_orders": (("order_number",),),
                "purchase_receipts": (
                    ("receipt_reference",),
                    ("purchase_order_id", "idempotency_key"),
                ),
            }.get(collection_name, ())
            self.collections[collection_name] = FakeCollection(unique_fields)
        return self.collections[collection_name]
