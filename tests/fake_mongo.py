"""Small in-memory MongoDB collection fake for Phase 3A unit tests.

Supports the subset of PyMongo operations used by organization and seat
services: equality/operator queries, ``$or``, projections, sorting,
``$set``/``$setOnInsert``/``$inc``/``$unset``, upserts, and atomic
``find_one_and_update``. It is intentionally not a general database.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable, Optional
from uuid import uuid4


@dataclass
class FakeUpdateResult:
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: Optional[str] = None
    deleted_count: int = 0


def _get(doc: dict, key: str) -> Any:
    current: Any = doc
    for part in key.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _set(doc: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    current = doc
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


def _unset(doc: dict, key: str) -> None:
    parts = key.split(".")
    current = doc
    for part in parts[:-1]:
        current = current.get(part)
        if not isinstance(current, dict):
            return
    current.pop(parts[-1], None)


def _match_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict) and any(str(k).startswith("$") for k in expected):
        for op, value in expected.items():
            if op == "$in":
                if actual not in value:
                    return False
            elif op == "$nin":
                if actual in value:
                    return False
            elif op == "$ne":
                if actual == value:
                    return False
            elif op == "$lt":
                if actual is None or not actual < value:
                    return False
            elif op == "$lte":
                if actual is None or not actual <= value:
                    return False
            elif op == "$gt":
                if actual is None or not actual > value:
                    return False
            elif op == "$gte":
                if actual is None or not actual >= value:
                    return False
            elif op == "$exists":
                exists = actual is not None
                if bool(value) != exists:
                    return False
            else:
                return False
        return True
    return actual == expected


def match(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        if key == "$or":
            if not any(match(document, sub) for sub in expected):
                return False
            continue
        if key == "$and":
            if not all(match(document, sub) for sub in expected):
                return False
            continue
        actual = _get(document, key)
        if not _match_value(actual, expected):
            return False
    return True


def project(document: dict, projection: Optional[dict]) -> dict:
    if not projection:
        return copy.deepcopy(document)
    include = {k for k, v in projection.items() if v and not str(k).startswith("$")}
    if not include:
        return copy.deepcopy(document)
    result = {"_id": document.get("_id")}
    for key in include:
        if key in document:
            result[key] = copy.deepcopy(document[key])
    return result


def _sort_documents(docs: list[dict], sort: Any) -> list[dict]:
    if not sort:
        return docs
    if isinstance(sort, str):
        sort = [(sort, 1)]
    for key, direction in reversed(list(sort)):
        docs = sorted(
            docs,
            key=lambda doc: (_get(doc, key) is None, _get(doc, key)),
            reverse=direction == -1,
        )
    return docs


class FakeCursor:
    def __init__(self, documents: Iterable[dict]):
        self._documents = list(documents)

    def sort(self, key_or_list: Any, direction: Optional[int] = None) -> "FakeCursor":
        sort = key_or_list if direction is None else [(key_or_list, direction)]
        self._documents = _sort_documents(self._documents, sort)
        return self

    def skip(self, count: int) -> "FakeCursor":
        self._documents = self._documents[max(0, count):]
        return self

    def limit(self, count: int) -> "FakeCursor":
        self._documents = self._documents[: max(0, count)]
        return self

    def __iter__(self):
        return iter(self._documents)

    def __len__(self):
        return len(self._documents)


class FakeCollection:
    def __init__(self):
        self.documents: list[dict] = []

    def insert_one(self, document: dict) -> FakeUpdateResult:
        doc = copy.deepcopy(document)
        doc.setdefault("_id", str(uuid4()))
        self.documents.append(doc)
        return FakeUpdateResult(matched_count=1, modified_count=1)

    def count_documents(self, query: dict) -> int:
        return sum(1 for doc in self.documents if match(doc, query))

    def find(
        self,
        query: Optional[dict] = None,
        projection: Optional[dict] = None,
        sort: Any = None,
    ) -> FakeCursor:
        query = query or {}
        docs = [project(doc, projection) for doc in self.documents if match(doc, query)]
        return FakeCursor(_sort_documents(docs, sort))

    def find_one(
        self,
        query: Optional[dict] = None,
        projection: Optional[dict] = None,
        sort: Any = None,
    ) -> Optional[dict]:
        cursor = self.find(query or {}, projection, sort)
        for doc in cursor:
            return doc
        return None

    def _apply_update(self, doc: dict, update: dict, inserting: bool) -> None:
        for op, values in update.items():
            if op == "$set":
                for key, value in values.items():
                    _set(doc, key, copy.deepcopy(value))
            elif op == "$setOnInsert":
                if inserting:
                    for key, value in values.items():
                        _set(doc, key, copy.deepcopy(value))
            elif op == "$inc":
                for key, value in values.items():
                    _set(doc, key, (_get(doc, key) or 0) + value)
            elif op == "$unset":
                for key in values:
                    _unset(doc, key)

    def _upsert_document(self, query: dict) -> dict:
        doc: dict = {}
        for key, value in query.items():
            if not str(key).startswith("$") and not isinstance(value, dict):
                _set(doc, key, copy.deepcopy(value))
        doc.setdefault("_id", str(uuid4()))
        return doc

    def update_one(
        self,
        query: dict,
        update: dict,
        upsert: bool = False,
        return_document: Any = False,
    ) -> FakeUpdateResult:
        for doc in self.documents:
            if match(doc, query):
                before = copy.deepcopy(doc)
                self._apply_update(doc, update, inserting=False)
                return FakeUpdateResult(
                    matched_count=1,
                    modified_count=0 if before == doc else 1,
                )
        if not upsert:
            return FakeUpdateResult()
        doc = self._upsert_document(query)
        self._apply_update(doc, update, inserting=True)
        self.documents.append(doc)
        return FakeUpdateResult(matched_count=0, modified_count=1, upserted_id=doc["_id"])

    def find_one_and_update(
        self,
        query: dict,
        update: dict,
        return_document: Any = False,
        **kwargs,
    ) -> Optional[dict]:
        for doc in self.documents:
            if match(doc, query):
                before = copy.deepcopy(doc)
                self._apply_update(doc, update, inserting=False)
                wants_after = return_document is True or str(return_document).endswith("AFTER")
                return copy.deepcopy(doc if wants_after else before)
        if kwargs.get("upsert"):
            doc = self._upsert_document(query)
            self._apply_update(doc, update, inserting=True)
            self.documents.append(doc)
            return copy.deepcopy(doc)
        return None

    def update_many(self, query: dict, update: dict) -> FakeUpdateResult:
        modified = 0
        for doc in self.documents:
            if match(doc, query):
                before = copy.deepcopy(doc)
                self._apply_update(doc, update, inserting=False)
                if before != doc:
                    modified += 1
        return FakeUpdateResult(matched_count=modified, modified_count=modified)

    def delete_one(self, query: dict) -> FakeUpdateResult:
        for index, doc in enumerate(self.documents):
            if match(doc, query):
                self.documents.pop(index)
                return FakeUpdateResult(matched_count=1, deleted_count=1)
        return FakeUpdateResult()

    def delete_many(self, query: dict) -> FakeUpdateResult:
        kept = [doc for doc in self.documents if not match(doc, query)]
        deleted = len(self.documents) - len(kept)
        self.documents = kept
        return FakeUpdateResult(matched_count=deleted, deleted_count=deleted)


class FakeMongo:
    def __init__(self):
        self.collections: dict[str, FakeCollection] = {}

    def collection(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())

    def get_mongodb_collection(self, name: str) -> FakeCollection:
        return self.collection(name)

    def seed(self, name: str, *documents: dict) -> None:
        collection = self.collection(name)
        for document in documents:
            collection.insert_one(document)
