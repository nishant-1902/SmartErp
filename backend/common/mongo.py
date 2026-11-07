"""Shared helpers for common, bounded MongoDB operations."""

from typing import Any

from pymongo.collection import Collection


def count_query_matches(
    collection: Collection[Any],
    query: dict[str, Any],
) -> int:
    """Count matching documents, scanning the small _id index for empty filters."""
    kwargs = {"hint": "_id_"} if not query else {}
    return collection.count_documents(query, **kwargs)
