from django.contrib import admin

from .models import DataSource, ImportBatch, Loan


@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "country", "version", "period")
    list_filter = ("kind",)


@admin.register(Loan)
class LoanAdmin(admin.ModelAdmin):
    list_display = ("loan_id", "source", "grade", "loan_amount", "interest_rate", "status", "issue_date")
    list_filter = ("source", "grade", "status", "purpose")
    search_fields = ("loan_id",)


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("filename", "source", "rows_read", "rows_imported", "rows_duplicate", "rows_rejected", "created_at")
