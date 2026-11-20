# campus-api-python Quick Reference

The user-facing Python SDK for the Campus platform. User-facing docs
are a MkDocs Material site (mkdocstrings auto-generates the API
reference from Google-style docstrings) published to GitHub Pages.

## Docs workflow

```bash
poetry run mkdocs build --strict   # docs-rot gate: same check CI runs on every PR
poetry run mkdocs serve            # local preview at http://127.0.0.1:8000
```

- API reference pages (`docs/reference/*.md`) use mkdocstrings
  `:::` directives — they follow the code automatically. Write
  docstrings, not reference prose. Undocumented public members still
  render (heading + signature), so a missing docstring is a visible
  docs gap, not an invisible one.
- Griffe runs in static (AST) mode: service packages need `__init__.py`
  markers (they have them); dynamic inspection is avoided because it
  materializes interpreter dunders on 3.13+ (see mkdocs.yml).

## Version bumps must ship with up-to-date docs

**Rule: every version bump must have up-to-date docs.** After
`poetry version ...`:

1. Run `poetry run python scripts/sync_docs_version.py` — regenerates
   `docs/snippets/version.md` (the stamp on the landing page).
2. Update any guides/examples (`docs/*.md`) the bump affects, and the
   README install snippet if it pins an old wheel version.
3. Commit both together.

CI enforces this: the `docs` job regenerates the stamp and fails on
`git diff --exit-code -- docs/`, and `mkdocs build --strict` fails on
broken links/refs. A bump without docs cannot merge.

Releases: bump + merge, then `git tag -a vX.Y.Z -m "<notes>"` (the
annotated tag message is the release body); the docs stamp and the
release must carry the same version.
