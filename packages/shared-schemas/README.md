# Shared schemas

JSON Schemas for the structured AI output contracts, generated from the Pydantic
validators in `apps/worker/pipeline/validate.py` (the single source of truth):

| File | Used for |
|---|---|
| `article_generation.schema.json` | One news batch: `{"articles": [...]}` (plan section 6 contract, wrapped for 1-3 stories per call) |
| `crunch_output.schema.json` | One Crunch result: bullets, sections, mnemonics, traps, flashcards - all with source refs |
| `*.inline.schema.json` | Same schemas with `$ref`s inlined (the form sent to Gemini `responseJsonSchema` / Groq `json_schema`) |

Regenerate after changing the validators:

```bash
uv run python scripts/export_schemas.py
```

A schema-valid response is not considered verified: the worker additionally checks
that every cited source id was actually provided, that numbers appear in the
evidence, that claims overlap the evidence text, and that quiz answers are supported.
