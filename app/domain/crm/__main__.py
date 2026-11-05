import argparse
import csv
from pathlib import Path

from app.core.db.session import SessionFactory
from app.domain.crm.imports import parse_export, stage_export


def main():
    parser = argparse.ArgumentParser(description="Stage Airtable CRM CSV exports.")
    parser.add_argument("--mah", type=Path)
    parser.add_argument("--contacts", type=Path)
    parser.add_argument("--end-users", type=Path)
    parser.add_argument("--it-suppliers", type=Path)
    args = parser.parse_args()
    sources = (
        ("MAH", args.mah),
        ("Contacts", args.contacts),
        ("End Users", args.end_users),
        ("IT Suppliers", args.it_suppliers),
    )
    if not any(path for _, path in sources):
        parser.error("Provide at least one Airtable export.")
    imports = []
    try:
        for table, path in sources:
            if path is None:
                continue
            content = path.read_bytes()
            imports.append((parse_export(table, content), content, path.name))
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"Cannot stage exports: {exc}\n")
    with SessionFactory() as session:
        results = [
            (staged.id, dataset.source_dataset_name, staged.row_count, created)
            for dataset, content, filename in imports
            for staged, created in [stage_export(session, dataset, content, filename)]
        ]
        session.commit()
    for identifier, table, count, created in results:
        print(
            f"{table}: {count} records · staging dataset {identifier} · {'staged' if created else 'already staged'}"
        )


if __name__ == "__main__":
    main()
