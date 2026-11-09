from django.db import models


class Borrower(models.Model):
    """Anonymised borrower reference.

    Public lending datasets (e.g. LendingClub) do not expose borrower
    identity; this table only stores the dataset's own anonymised key when
    one exists. No names, contact details or government IDs are stored.
    """

    source = models.ForeignKey(
        "lending_data.DataSource", on_delete=models.CASCADE, related_name="borrowers"
    )
    external_id = models.CharField(max_length=64, help_text="Anonymised key from the source dataset")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "external_id"], name="uniq_borrower_per_source")
        ]

    def __str__(self) -> str:
        return f"{self.source_id}:{self.external_id}"
