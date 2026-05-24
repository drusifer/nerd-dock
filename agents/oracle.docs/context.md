# Agent Local Context — Oracle

> ## Recent Decisions
> - **[2026-05-24] Documenting Ecosystem Controls:** Created comprehensive repository frontpage (`README.md`) and extensive user-facing guide (`docs/USER_GUIDE.md`) to clearly outline GTK GObject Introspection bindings, multi-thread idle loops, standard CLI option mappings, and desktop keyboard shortcuts (hotkey integration) for standard GNOME desktop configurations.
> - **[2026-05-24] Documentation Index Consolidation:** Updated the main documentation index `agents/DOCUMENTATION_INDEX.md` to link directly to project specs (`docs/PRD.md`, `docs/ARCH.md`, `docs/USER_STORIES.md`) and the new user guide.
>
> ## Key Findings
> - **Virtual Environment System Linkage:** Discovered that PyGObject requires `--system-site-packages` on setup to correctly interface with native binary system resources on Ubuntu.
> - **Desktop State Synchronization:** Detailed the background monitor's capability of checking process states via cookie files and `/proc/<pid>/status` directly, syncing shell triggers without UI lag.
>
> ## Important Notes
> - Keep references to `docs/PRD.md` and `docs/ARCH.md` unified when updating user documents.
> - Ensure all manual/automated instructions reflect the Python system package venv environment pipeline.
>
>---
>*Last updated: 2026-05-24T12:05:00-04:00*
