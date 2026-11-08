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
    parser.add_argument("--agreements", type=Path)
    parser.add_argument("--self-declarations", type=Path)
    parser.add_argument("--download-agreement-pdfs", action="store_true")
    args = parser.parse_args()
    if args.download_agreement_pdfs and not args.agreements:
        parser.error("--download-agreement-pdfs requires --agreements.")
    sources = (
        ("MAH", args.mah),
        ("Contacts", args.contacts),
        ("End Users", args.end_users),
        ("IT Suppliers", args.it_suppliers),
        ("MAH Agreements", args.agreements),
        ("Self-declarations", args.self_declarations),
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
        if args.self_declarations:
            from app.domain.crm.self_declarations import seed_self_declarations

            dataset_id = next(
                identifier
                for identifier, table, _, _ in results
                if table == "Self-declarations"
            )
            declaration_count = seed_self_declarations(session, dataset_id)
        session.commit()
    for identifier, table, count, created in results:
        print(
            f"{table}: {count} records · staging dataset {identifier} · {'staged' if created else 'already staged'}"
        )

    if args.self_declarations:
        print(f"{declaration_count} self-declarations created.")

    if args.download_agreement_pdfs:
        from app.domain.crm.agreements import archive_pdfs

        agreements = next(
            dataset
            for dataset, _, _ in imports
            if dataset.source_dataset_name == "MAH Agreements"
        )
        if archive_pdfs(SessionFactory, agreements.rows):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
