# Roadmap and status

| Phase | Scope | Status |
|---|---|---|
| 0 | Scaffold, settings, env | Done |
| 1 | Models, importer, parsing | Done; importer tests need pandas (blocked on dev machine) |
| 2 | Cleaning pipeline (pandas) | Not started - needs pandas |
| 3 | Risk / return / portfolio services, API | Done, 15 tests pass |
| 3b | India rule checks | Done, rules marked unverified |
| 4 | ML default model (leakage-safe) | Not started - needs pandas and real data |
| 5 | Docker | Files written, **not built or run** |
| 6 | Power BI DAX, M, theme | Written, **not opened in Power BI**; page specs pending |
| 7 | 4 decks, report, SRS etc. | Not started |

## Open questions
1. Pandas blocked by Windows Application Control (`ccalendar` DLL) - allow-list `.venv` or use Docker.
2. LendingClub CSV: which file/version, and licence confirmation.
3. Include the optional synthetic India demo dataset?
4. Review dates and institute report template.
5. SQLite vs PostgreSQL for Power BI refresh.
6. Verify RBI figures against RBI/2024-25/63.
