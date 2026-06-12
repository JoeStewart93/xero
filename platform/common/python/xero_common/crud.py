from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


def create(session: Session, instance: ModelT) -> ModelT:
    session.add(instance)
    session.flush()
    session.refresh(instance)
    return instance


def read(session: Session, model: type[ModelT], entity_id: object) -> ModelT | None:
    return session.get(model, entity_id)


def list_all(session: Session, model: type[ModelT], *, offset: int = 0, limit: int = 100) -> list[ModelT]:
    statement = select(model).offset(offset).limit(limit)
    return list(session.scalars(statement).all())


def update(session: Session, instance: ModelT, **fields: Any) -> ModelT:
    for name, value in fields.items():
        setattr(instance, name, value)
    session.add(instance)
    session.flush()
    session.refresh(instance)
    return instance


def delete(session: Session, instance: ModelT) -> None:
    session.delete(instance)
    session.flush()
