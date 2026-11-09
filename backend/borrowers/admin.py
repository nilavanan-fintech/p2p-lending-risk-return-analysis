from django.contrib import admin

from .models import Borrower


@admin.register(Borrower)
class BorrowerAdmin(admin.ModelAdmin):
    list_display = ("external_id", "source")
    search_fields = ("external_id",)
