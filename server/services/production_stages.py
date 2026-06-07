"""10 этапов производства на компонент (ТЗ file-008)."""

from __future__ import annotations

from datetime import date as dt_date

from sqlalchemy.orm import Session

from models.award import ProductionComponentReady, ProductionStageRow

PRODUCTION_STAGES: list[tuple[str, str]] = [
    ("def_control", "Определение контроля"),
    ("layout_rework", "Доработка макета"),
    ("layout_approval", "Согласование макета"),
    ("order", "Заказ"),
    ("payment", "Оплата"),
    ("sample", "Сигнальный образец"),
    ("design_rework", "Доработка дизайна"),
    ("production_design", "Дизайн для производства"),
    ("production", "Производство"),
    ("delivery", "Поставка"),
]

STAGE_RU_TO_KEY: dict[str, str] = {
    "опред контр": "def_control",
    "доработка макета": "layout_rework",
    "согласование макета": "layout_approval",
    "заказ": "order",
    "оплата": "payment",
    "сигнальный образец": "sample",
    "доработка дизайна": "design_rework",
    "дизайн для производства": "production_design",
    "производство": "production",
    "поставка": "delivery",
}

STAGE_KEY_TO_RU = {k: v for k, v in PRODUCTION_STAGES}

FIELD_SUFFIX_TO_ATTR = {
    "статус": "status",
    "дата": "stage_date",
    "вложение": "attachment_note",
}


def stage_label(stage_key: str) -> str:
    return STAGE_KEY_TO_RU.get(stage_key, stage_key)


def _ready_row(db: Session, award_id: int, component_type: str) -> ProductionComponentReady | None:
    return (
        db.query(ProductionComponentReady)
        .filter(
            ProductionComponentReady.award_id == award_id,
            ProductionComponentReady.component_type == component_type,
        )
        .first()
    )


def _stage_rows(db: Session, award_id: int, component_type: str) -> dict[str, ProductionStageRow]:
    rows = (
        db.query(ProductionStageRow)
        .filter(
            ProductionStageRow.award_id == award_id,
            ProductionStageRow.component_type == component_type,
        )
        .all()
    )
    return {r.stage_key: r for r in rows}


PRODUCTION_STAGE_STATUSES = [
    "",
    "Не начато",
    "В работе",
    "Ожидание",
    "Завершено",
    "Отменено",
]


def component_payload(db: Session, award_id: int, component_type: str) -> dict:
    from services.production_stage_files import attachment_counts_for_component

    by_key = _stage_rows(db, award_id, component_type)
    ready = _ready_row(db, award_id, component_type)
    att_counts = attachment_counts_for_component(db, award_id, component_type)
    stages = []
    for key, label in PRODUCTION_STAGES:
        row = by_key.get(key)
        stages.append({
            "stage_key": key,
            "label": label,
            "status": row.status if row else None,
            "stage_date": row.stage_date if row else None,
            "attachment_note": row.attachment_note if row else None,
            "attachment_count": att_counts.get(key, 0),
        })
    return {
        "component_type": component_type,
        "is_ready": bool(ready.is_ready) if ready else False,
        "stages": stages,
    }


def list_components_for_award(db: Session, award_id: int, component_types: list[str]) -> dict:
    return {
        "components": [
            component_payload(db, award_id, ct) for ct in component_types
        ],
    }


def upsert_component(
    db: Session,
    award_id: int,
    component_type: str,
    *,
    is_ready: bool | None = None,
    stages: list[dict] | None = None,
) -> dict:
    if stages:
        by_key = _stage_rows(db, award_id, component_type)
        valid_keys = {k for k, _ in PRODUCTION_STAGES}
        for item in stages:
            key = (item.get("stage_key") or "").strip()
            if key not in valid_keys:
                continue
            row = by_key.get(key)
            if row is None:
                row = ProductionStageRow(
                    award_id=award_id,
                    component_type=component_type,
                    stage_key=key,
                )
                db.add(row)
            status = item.get("status")
            row.status = (status or "").strip() or None if status is not None else row.status
            sd = item.get("stage_date")
            if sd is not None:
                if isinstance(sd, str) and not sd.strip():
                    row.stage_date = None
                else:
                    row.stage_date = sd
            att = item.get("attachment_note")
            if att is not None:
                row.attachment_note = (att or "").strip() or None

    if is_ready is not None:
        ready = _ready_row(db, award_id, component_type)
        if ready is None:
            ready = ProductionComponentReady(
                award_id=award_id,
                component_type=component_type,
                is_ready=bool(is_ready),
            )
            db.add(ready)
        else:
            ready.is_ready = bool(is_ready)

    return component_payload(db, award_id, component_type)


def parse_production_column(header: str) -> tuple[str, str] | None:
    """ПРОИЗВ_медаль_опред контр_статус -> (stage_key, field_attr)."""
    h = (header or "").strip()
    if not h.startswith("ПРОИЗВ_"):
        return None
    for suffix, attr in FIELD_SUFFIX_TO_ATTR.items():
        if not h.endswith(f"_{suffix}"):
            continue
        body = h[len("ПРОИЗВ_") : -len(f"_{suffix}")]
        if "_" not in body:
            continue
        stage_ru = body.split("_", 1)[1].strip().lower()
        key = STAGE_RU_TO_KEY.get(stage_ru)
        if key:
            return key, attr
    return None
