from unittest.mock import Mock

from common.mongo import count_query_matches


def test_empty_count_uses_id_index_hint():
    collection = Mock()
    collection.count_documents.return_value = 15

    result = count_query_matches(collection, {})

    assert result == 15
    collection.count_documents.assert_called_once_with({}, hint="_id_")


def test_filtered_count_leaves_index_selection_to_mongodb():
    collection = Mock()
    collection.count_documents.return_value = 3
    query = {"status": "active"}

    result = count_query_matches(collection, query)

    assert result == 3
    collection.count_documents.assert_called_once_with(query)
