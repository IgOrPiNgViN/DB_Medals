"""Полная копия строк выгрузки Access (CSV) для просмотра «как в исходной БД»."""

from sqlalchemy import Column, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from database import Base


class AccessMirrorRow(Base):
    """Одна строка исходной таблицы Access (имя = имя файла CSV без .csv)."""

    __tablename__ = "access_mirror_rows"
    __table_args__ = (
        UniqueConstraint("table_name", "row_index", name="uq_access_mirror_table_row"),
    )

    id = Column(Integer, primary_key=True, index=True)
    table_name = Column(String(512), nullable=False, index=True)
    row_index = Column(Integer, nullable=False)
    data = Column(JSONB, nullable=False)
