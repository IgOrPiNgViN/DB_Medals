"""
Извлекает изображения из Access (поле Изображение таблицы НаградыМега)
и сохраняет их в папку migration/extracted_images/.

Запуск:
  python migration/export_images.py
"""
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parent.parent


def parse_attachment(raw: bytes) -> bytes:
    """Access Attachment header: first 4 bytes = uint32 LE header size."""
    if len(raw) < 4:
        return raw
    hdr = struct.unpack_from("<I", raw, 0)[0]
    return raw[hdr:] if hdr < len(raw) else raw


def safe_filename(name: str) -> str:
    bad = r'/\:*?"<>|'
    for ch in bad:
        name = name.replace(ch, "-")
    return name[:80].strip()


def main():
    try:
        import win32com.client as w32
    except ImportError:
        print("pywin32 не установлен: pip install pywin32")
        sys.exit(1)

    # Найти первый подходящий .accdb
    candidates = [f for f in sorted(ROOT.glob("*.accdb"))
                  if "архив" not in f.name.lower()]
    if not candidates:
        candidates = list(ROOT.glob("*.accdb"))
    if not candidates:
        print("Файл .accdb не найден")
        sys.exit(1)

    accdb = candidates[0]
    print(f"База: {accdb.name}")

    out_dir = ROOT / "migration" / "extracted_images"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Куда: {out_dir}\n")

    engine = w32.Dispatch("DAO.DBEngine.120")
    db = engine.OpenDatabase(str(accdb))

    # Найти таблицу НаградыМега
    target = next(
        (t for t in db.TableDefs if "награды" in t.Name.lower()),
        None,
    )
    if target is None:
        print("Таблица НаградыМега не найдена")
        db.Close()
        sys.exit(1)

    print(f"Таблица: {target.Name}")

    # Attachment-поля
    ATT = 101
    att_fields = [f.Name for f in target.Fields if f.Type == ATT]
    print(f"Поля-вложения: {att_fields}\n")

    rs = db.OpenRecordset(target.Name)
    saved = 0

    if not (rs.BOF and rs.EOF):
        rs.MoveFirst()
        while not rs.EOF:
            name = (rs.Fields("Название награды").Value or "").strip()

            for field_name in att_fields:
                try:
                    att = rs.Fields(field_name).Value
                    if att.BOF and att.EOF:
                        att.Close()
                        continue

                    att.MoveFirst()
                    while not att.EOF:
                        fname = att.Fields("FileName").Value or "image.jpg"
                        raw_data = att.Fields("FileData").Value
                        if raw_data:
                            data = parse_attachment(bytes(raw_data))
                            if data:
                                safe = safe_filename(name)
                                ext = Path(fname).suffix or ".jpg"
                                # Добавляем суффикс поля если их несколько
                                field_suffix = ""
                                if len(att_fields) > 1:
                                    field_suffix = "_" + field_name.replace(" ", "_")
                                out_path = out_dir / f"{safe}{field_suffix}{ext}"
                                out_path.write_bytes(data)
                                fmt = "PNG" if data[:8] == b"\x89PNG\r\n\x1a\n" else (
                                    "JPEG" if data[:2] == b"\xff\xd8" else "?"
                                )
                                print(f"  [OK] {out_path.name}  {fmt}  {len(data):,} bytes")
                                saved += 1
                        att.MoveNext()
                    att.Close()
                except Exception as e:
                    print(f"  [WARN] {field_name}: {e}")

            rs.MoveNext()

    rs.Close()
    db.Close()

    print(f"\nСохранено: {saved} файлов -> {out_dir}")


if __name__ == "__main__":
    main()
