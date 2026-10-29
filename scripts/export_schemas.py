"""Writes the AI output JSON Schemas (the contract the worker validates) to packages/shared-schemas.

uv run python scripts/export_schemas.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.providers.base import inline_schema
from pipeline.validate import CrunchOut, NewsBatchOut

OUT = Path(__file__).resolve().parents[1] / "packages" / "shared-schemas"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, model in (("article_generation", NewsBatchOut), ("crunch_output", CrunchOut)):
        schema = model.model_json_schema()
        (OUT / f"{name}.schema.json").write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
        (OUT / f"{name}.inline.schema.json").write_text(
            json.dumps(inline_schema(schema), indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
