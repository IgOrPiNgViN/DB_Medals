"""Стандартные комплекты наград (ТЗ: медаль + значок + удостоверение + коробка и т.д.)."""

from sqlalchemy.orm import Session

from models.award import Award, AwardType, ComponentType, InventoryItem

# Базовый состав комплекта по виду награды
KIT_BY_AWARD_TYPE: dict[AwardType, list[ComponentType]] = {
    AwardType.MEDAL: [
        ComponentType.MEDAL,
        ComponentType.BADGE,
        ComponentType.CERTIFICATE,
        ComponentType.BOX,
    ],
    AwardType.PPZ: [
        ComponentType.PPZ,
        ComponentType.CERTIFICATE,
        ComponentType.BOX,
    ],
    AwardType.DISTINCTION: [
        ComponentType.BADGE,
        ComponentType.CERTIFICATE,
    ],
    AwardType.DECORATION: [
        ComponentType.PENDANT,
        ComponentType.CERTIFICATE,
        ComponentType.BOX,
    ],
}


def kit_components_for_award(award: Award, kit_type_label: str | None = None) -> list[ComponentType]:
    """Компоненты для резерва/списания; при указании типа комплекта — только ППЗ/медаль."""
    base = list(KIT_BY_AWARD_TYPE.get(award.award_type, [ComponentType.CERTIFICATE]))
    label = (kit_type_label or "").strip().lower()
    if not label:
        return base
    if "ппз" in label and ComponentType.PPZ in base:
        return [ComponentType.PPZ, ComponentType.CERTIFICATE, ComponentType.BOX]
    if "медал" in label:
        filtered = [c for c in base if c != ComponentType.PPZ]
        return filtered or base
    return base


def ensure_inventory_kit(db: Session, award_id: int, award_type: AwardType) -> None:
    """Создать строки склада для всех компонентов комплекта, если их ещё нет."""
    rows = db.query(InventoryItem).filter(InventoryItem.award_id == award_id).all()
    existing = {row.component_type for row in rows}
    for component in KIT_BY_AWARD_TYPE.get(award_type, [ComponentType.CERTIFICATE]):
        if component in existing:
            continue
        db.add(
            InventoryItem(
                award_id=award_id,
                component_type=component,
                total_count=100,
                reserve_count=0,
                issued_count=0,
                available_count=100,
            )
        )
