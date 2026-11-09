from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from lending_data.models import DataSource
from lending_data.services.importer import import_file


class Command(BaseCommand):
    help = "Import a LendingClub-schema CSV/XLSX file into a named DataSource."

    def add_arguments(self, parser):
        parser.add_argument("path", type=Path)
        parser.add_argument("--source", required=True, help="DataSource name (created if absent)")
        parser.add_argument("--kind", choices=[k for k, _ in DataSource.Kind.choices], default="observed")
        parser.add_argument("--country", default="")
        parser.add_argument("--version", default="")
        parser.add_argument("--period", default="")
        parser.add_argument("--url", default="")
        parser.add_argument("--licence", default="")

    def handle(self, *args, **o):
        if not o["path"].exists():
            raise CommandError(f"File not found: {o['path']}")
        source, created = DataSource.objects.get_or_create(
            name=o["source"],
            defaults={k: o[k] for k in ("kind", "country", "version", "period", "url", "licence")},
        )
        if not created and source.kind != o["kind"]:
            raise CommandError(f"Source {source.name!r} already exists with kind {source.kind!r}")
        try:
            res = import_file(o["path"], source)
        except ValueError as exc:
            raise CommandError(str(exc))
        b = res.batch
        self.stdout.write(self.style.SUCCESS(
            f"read={b.rows_read} imported={b.rows_imported} duplicates={b.rows_duplicate} rejected={b.rows_rejected}"
        ))
        if b.missing_columns:
            self.stdout.write(f"Columns absent from file (left empty, not fabricated): {b.missing_columns}")
        for e in res.errors[:10]:
            self.stdout.write(self.style.WARNING(e))
