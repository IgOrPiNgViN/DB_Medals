"""Сводка склада по наградам — колонки как в ТЗ (file-011)."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from models.award import Award, AwardKitStock, AwardType, ComponentType, InventoryItem

# Поля характеристик Access (НаградыМega.csv) → ключи ответа API
_MEDAL_CHAR_MAP = {
    "Количество комплектов": "sets",
    "М - Количество медалей": "medals",
    "М - Количество значков (золото)": "badge_gold",
    "М - Количество значков (серебро)": "badge_silver",
    "М - Количество значков (з-с)": "badge_gold_silver",
    "М - Количество значков (латунь)": "badge_brass",
    "М - Количество удостоверений": "certificates",
    "М - Количество коробок под медали": "boxes",
    "Количество запонок": "cufflinks",
    "Количество коробок под запонки": "cufflink_boxes",
    "Количество кулонов": "pendants",
    "Количество цепочек": "chains",
    "Количество коробок под кулоны": "pendant_boxes",
}

_PPZ_CHAR_MAP = {
    "Количество комплектов": "sets",
    "П - Количество ППЗ": "ppz",
    "П - Количество удостов ППЗ": "certificates",
    "П - Количество значков": "badges",
    "П - Количество коробок под ППЗ": "boxes",
}


def _char_map(award_type: AwardType | None) -> dict[str, str]:
    if award_type == AwardType.PPZ:
        return _PPZ_CHAR_MAP
    if award_type == AwardType.DECORATION:
        return {
            "Количество запонок": "cufflinks",
            "Количество коробок под запонки": "cufflink_boxes",
            "Количество кулонов": "pendants",
            "Количество цепочек": "chains",
            "Количество коробок под кулоны": "pendant_boxes",
        }
    return _MEDAL_CHAR_MAP


def _parse_int(val) -> int:
    if val is None or val == "":
        return 0
    try:
        return int(float(str(val).replace(",", ".").strip()))
    except (TypeError, ValueError):
        return 0


def _inv_available(items: list[InventoryItem], ct: ComponentType) -> int:
    total = 0
    for it in items:
        if it.component_type == ct:
            total += it.available_count or 0
    return total


def _aggregate_award(award: Award) -> dict:
    items = list(award.inventory_items or [])
    chars = {c.field_name: c.field_value for c in (award.characteristics or [])}
    cmap = _char_map(award.award_type)

    row: dict = {
        "award_id": award.id,
        "award_name": award.name,
        "award_type": award.award_type.value if award.award_type else None,
        "low_stock": False,
    }

    for char_name, key in cmap.items():
        row[key] = _parse_int(chars.get(char_name))

    stock: AwardKitStock | None = award.kit_stock
    if stock and (stock.physical_sets or 0) > 0:
        row["sets"] = stock.physical_sets

    # Живые остатки склада имеют приоритет над статикой из характеристик
    if award.award_type == AwardType.PPZ:
        ppz = _inv_available(items, ComponentType.PPZ)
        if ppz:
            row["ppz"] = ppz
        cert = _inv_available(items, ComponentType.CERTIFICATE)
        if cert:
            row["certificates"] = cert
        box = _inv_available(items, ComponentType.BOX)
        if box:
            row["boxes"] = box
        badge = _inv_available(items, ComponentType.BADGE)
        if badge:
            row["badges"] = badge
    elif award.award_type == AwardType.DECORATION:
        for ct, key in (
            (ComponentType.CUFFLINKS, "cufflinks"),
            (ComponentType.PENDANT, "pendants"),
            (ComponentType.BOX, "boxes"),
        ):
            v = _inv_available(items, ct)
            if v:
                row[key] = v
    else:
        med = _inv_available(items, ComponentType.MEDAL)
        if med:
            row["medals"] = med
        cert = _inv_available(items, ComponentType.CERTIFICATE)
        if cert:
            row["certificates"] = cert
        box = _inv_available(items, ComponentType.BOX)
        if box:
            row["boxes"] = box
        badge_total = _inv_available(items, ComponentType.BADGE)
        if badge_total and not any(
            row.get(k, 0)
            for k in ("badge_gold", "badge_silver", "badge_gold_silver", "badge_brass")
        ):
            row["badge_brass"] = badge_total

    nums = [v for k, v in row.items() if isinstance(v, int) and k not in ("award_id",)]
    row["low_stock"] = any(0 < v < 10 for v in nums)
    return row


_AWARD_TYPE_RU = {
    AwardType.MEDAL: "Медали",
    AwardType.PPZ: "ППЗ",
    AwardType.DISTINCTION: "Знаки отличия",
    AwardType.DECORATION: "Украшения",
}


def warehouse_summary_grouped(
    db: Session,
    award_type: str | None = None,
) -> list[dict]:
    q = db.query(Award).options(
        joinedload(Award.inventory_items),
        joinedload(Award.characteristics),
        joinedload(Award.kit_stock),
    )
    if award_type:
        try:
            q = q.filter(Award.award_type == AwardType(award_type))
        except ValueError:
            pass
    awards = q.order_by(Award.name).all()
    return [_aggregate_award(a) for a in awards]


def grouped_xlsx_headers(award_type: str | None) -> list[str]:
    if award_type == "ppz":
        return [
            "Награда", "Комплекты", "ППЗ", "Удостоверения", "Значки", "Коробки",
        ]
    if award_type == "decoration":
        return [
            "Награда", "Запонки", "Коробки (з)", "Кулоны", "Цепочки", "Коробки (к)",
        ]
    if award_type == "distinction":
        return ["Награда", "Значки", "Удостоверения"]
    return [
        "Награда",
        "Комплекты",
        "Медали",
        "Значки (з)",
        "Значки (с)",
        "Значки (з-с)",
        "Значки (л)",
        "Удостоверения",
        "Коробки",
    ]


def grouped_xlsx_row(item: dict) -> list:
    at = item.get("award_type")
    if at == "ppz":
        return [
            item.get("award_name"),
            item.get("sets", 0),
            item.get("ppz", 0),
            item.get("certificates", 0),
            item.get("badges", 0),
            item.get("boxes", 0),
        ]
    if at == "decoration":
        return [
            item.get("award_name"),
            item.get("cufflinks", 0),
            item.get("cufflink_boxes", 0),
            item.get("pendants", 0),
            item.get("chains", 0),
            item.get("pendant_boxes", 0),
        ]
    if at == "distinction":
        return [
            item.get("award_name"),
            item.get("badge_brass", 0) or item.get("badges", 0),
            item.get("certificates", 0),
        ]
    return [
        item.get("award_name"),
        item.get("sets", 0),
        item.get("medals", 0),
        item.get("badge_gold", 0),
        item.get("badge_silver", 0),
        item.get("badge_gold_silver", 0),
        item.get("badge_brass", 0),
        item.get("certificates", 0),
        item.get("boxes", 0),
    ]
