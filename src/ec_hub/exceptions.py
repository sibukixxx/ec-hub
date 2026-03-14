"""Business exceptions (HTTP-independent)."""

from __future__ import annotations


class NotFoundError(Exception):
    """Raised when a requested entity does not exist."""

    def __init__(self, entity: str, entity_id: int) -> None:
        self.entity = entity
        self.entity_id = entity_id
        super().__init__(f"{entity} not found: id={entity_id}")


class InvalidStatusError(Exception):
    """Raised when an invalid status value is given."""

    def __init__(self, status: str, valid: set[str]) -> None:
        self.status = status
        self.valid = valid
        super().__init__(f"Invalid status '{status}'. Must be one of: {valid}")
