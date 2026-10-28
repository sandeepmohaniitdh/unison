"""Pagination for every list: ?page=2&size=20 returns
{"items": [...], "page": 2, "size": 20, "total": 412}.

size is capped at 50, so nobody can ask for every row at once. Every list
has a fixed order (usually newest first), so items don't move between pages.
"""

from collections.abc import Callable
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

T = TypeVar("T")
MAX_SIZE = 50


class Page(BaseModel, Generic[T]):
    items: list[T]
    page: int = Field(examples=[1])
    size: int = Field(examples=[20])
    total: int = Field(description="Number of items on all pages together.", examples=[57])


class PageParams(BaseModel):
    page: int = 1
    size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


def _page_params(
    page: Annotated[int, Query(ge=1, description="Page number, from 1.")] = 1,
    size: Annotated[int, Query(ge=1, le=MAX_SIZE, description="Items per page, 1 to 50.")] = 20,
) -> PageParams:
    return PageParams(page=page, size=size)


Pagination = Annotated[PageParams, Depends(_page_params)]


def paginate(db: Session, stmt: Select, params: PageParams, to_item: Callable | None = None) -> dict:
    """Run a SELECT for one page and count all matching rows.

    `stmt` must already have its ORDER BY, so pages are stable.
    `to_item` turns one row into a response item; by default the row itself.
    """
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.execute(stmt.limit(params.size).offset(params.offset))
    if len(stmt.column_descriptions) == 1:  # select(Model) or select(column): one value per row
        rows = rows.scalars()
    items = [to_item(r) if to_item else r for r in rows.all()]
    return {"items": items, "page": params.page, "size": params.size, "total": total}


def page_of(items: list, params: PageParams) -> dict:
    """Paginate a list that is already in memory (short lists only)."""
    start = params.offset
    return {"items": items[start : start + params.size], "page": params.page, "size": params.size, "total": len(items)}
