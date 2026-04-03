import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.index_store import SQLiteIndexStore
from app.services.persons_shadow_importer import PersonsShadowImporter


def main() -> None:
    settings = get_settings()
    store = SQLiteIndexStore(settings.sqlite_db_path)
    importer = PersonsShadowImporter(store)

    seed_path = Path("docs/test-seed/seed.json")
    imported = importer.import_json_file(seed_path)
    print(f"Imported {imported} person cards from {seed_path}")


if __name__ == "__main__":
    main()
