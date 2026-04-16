"""API contract breaking-change 검사 스크립트 (v0.9).

FastAPI OpenAPI 스키마 스냅샷을 `docs/api-snapshots/current.json`과 비교하여
breaking change를 감지한다.

사용:
    python scripts/check_api_contracts.py             # 비교
    python scripts/check_api_contracts.py --update    # 스냅샷 갱신

Breaking 기준:
- 경로 삭제
- 메서드 삭제
- 필드 삭제
- required → optional 또는 optional → required 변환
- enum 값 삭제
- 타입 변경
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "docs" / "api-snapshots" / "current.json"


def _load_openapi() -> dict[str, Any]:
    """FastAPI 앱에서 현재 OpenAPI 스키마 추출."""
    sys.path.insert(0, str(ROOT / "apps" / "api"))
    from app.main import app  # type: ignore

    return app.openapi()


def _extract_contract(spec: dict[str, Any]) -> dict[str, Any]:
    """비교에 필요한 최소 계약만 추출."""
    paths = spec.get("paths", {})
    schemas = spec.get("components", {}).get("schemas", {})

    contract_paths: dict[str, dict[str, list[str]]] = {}
    for path, methods in paths.items():
        contract_paths[path] = {}
        for method, op in methods.items():
            if method.upper() not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            # request body schema ref
            req_schema = None
            req = op.get("requestBody", {}).get("content", {}).get("application/json", {})
            if req.get("schema", {}).get("$ref"):
                req_schema = req["schema"]["$ref"].split("/")[-1]
            # response schemas
            resp_schemas = []
            for code, resp in op.get("responses", {}).items():
                ref = resp.get("content", {}).get("application/json", {}).get("schema", {}).get("$ref")
                if ref:
                    resp_schemas.append({"code": code, "schema": ref.split("/")[-1]})
            contract_paths[path][method.upper()] = {
                "request_schema": req_schema,
                "responses": resp_schemas,
            }

    # 스키마 필드 목록
    contract_schemas = {}
    for name, schema in schemas.items():
        fields = {}
        required = set(schema.get("required", []))
        for field_name, field_def in schema.get("properties", {}).items():
            fields[field_name] = {
                "type": field_def.get("type") or field_def.get("$ref"),
                "required": field_name in required,
                "enum": field_def.get("enum"),
            }
        contract_schemas[name] = fields

    return {"paths": contract_paths, "schemas": contract_schemas}


def diff_contracts(old: dict, new: dict) -> list[str]:
    """old → new 비교 후 breaking change 리스트 반환."""
    breaks: list[str] = []

    # Paths
    for path, old_methods in old.get("paths", {}).items():
        if path not in new.get("paths", {}):
            breaks.append(f"BREAKING: path removed — {path}")
            continue
        new_methods = new["paths"][path]
        for method in old_methods:
            if method not in new_methods:
                breaks.append(f"BREAKING: method removed — {method} {path}")

    # Schemas
    for name, old_fields in old.get("schemas", {}).items():
        if name not in new.get("schemas", {}):
            breaks.append(f"BREAKING: schema removed — {name}")
            continue
        new_fields = new["schemas"][name]
        for field_name, old_def in old_fields.items():
            if field_name not in new_fields:
                breaks.append(f"BREAKING: field removed — {name}.{field_name}")
                continue
            new_def = new_fields[field_name]
            # required 변화
            if old_def.get("required") != new_def.get("required"):
                breaks.append(
                    f"BREAKING: required flag changed — {name}.{field_name} "
                    f"({old_def.get('required')} → {new_def.get('required')})"
                )
            # type 변화
            if old_def.get("type") and old_def["type"] != new_def.get("type"):
                breaks.append(
                    f"BREAKING: type changed — {name}.{field_name} "
                    f"({old_def['type']} → {new_def.get('type')})"
                )
            # enum 값 삭제
            if old_def.get("enum"):
                old_vals = set(old_def["enum"])
                new_vals = set(new_def.get("enum") or [])
                removed = old_vals - new_vals
                if removed:
                    breaks.append(
                        f"BREAKING: enum values removed — {name}.{field_name} lost {removed}"
                    )

    return breaks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update", action="store_true", help="update baseline snapshot")
    args = parser.parse_args()

    print("📋 Extracting current OpenAPI contract...")
    current = _extract_contract(_load_openapi())

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.update or not SNAPSHOT_PATH.exists():
        SNAPSHOT_PATH.write_text(json.dumps(current, indent=2, sort_keys=True, ensure_ascii=False))
        print(f"✅ Snapshot written: {SNAPSHOT_PATH.relative_to(ROOT)}")
        print(f"   paths={len(current['paths'])} schemas={len(current['schemas'])}")
        return 0

    baseline = json.loads(SNAPSHOT_PATH.read_text())
    breaks = diff_contracts(baseline, current)

    if breaks:
        print("❌ Breaking changes detected:")
        for b in breaks:
            print(f"  - {b}")
        print()
        print("   If intentional, run `python scripts/check_api_contracts.py --update`")
        print("   and document in docs/api-breaking-changes.md")
        return 1

    print("✅ No breaking changes against baseline")
    print(f"   paths={len(current['paths'])} schemas={len(current['schemas'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
