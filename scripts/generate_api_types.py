#!/usr/bin/env python3
"""OpenAPI → TypeScript 타입 자동 생성 스크립트 (v0.9).

FastAPI 서버의 OpenAPI 스키마에서 TypeScript 인터페이스를 자동 생성합니다.
생성된 파일은 packages/shared/src/generated/api-types.ts에 저장됩니다.

사용법:
    python scripts/generate_api_types.py
    # 또는 서버 URL 지정:
    python scripts/generate_api_types.py --url http://localhost:8000/api/v1/openapi.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트에서 실행
PROJECT_ROOT = Path(__file__).resolve().parents[1]
APPS_API_DIR = PROJECT_ROOT / "apps" / "api"
SHARED_DIR = PROJECT_ROOT / "packages" / "shared" / "src" / "generated"
OUTPUT_FILE = SHARED_DIR / "api-types.ts"


def get_openapi_schema(url: str | None = None) -> dict:
    """OpenAPI 스키마를 가져옵니다 (서버 또는 로컬 import)."""
    if url:
        import urllib.request
        with urllib.request.urlopen(url) as resp:
            return json.loads(resp.read())

    # 로컬 import — 서버 없이 스키마 추출
    sys.path.insert(0, str(APPS_API_DIR))
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
    os.environ.setdefault("LLM_PROVIDER", "mock")
    os.environ.setdefault("ENV", "development")
    os.environ.setdefault("JWT_SECRET_KEY", "generate-types-only")

    from app.main import app
    return app.openapi()


def openapi_type_to_ts(schema: dict, schemas: dict, indent: int = 0) -> str:
    """OpenAPI 스키마 타입을 TypeScript 타입 문자열로 변환."""
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return ref_name

    schema_type = schema.get("type")
    any_of = schema.get("anyOf")

    if any_of:
        types = []
        for sub in any_of:
            if sub.get("type") == "null":
                types.append("null")
            else:
                types.append(openapi_type_to_ts(sub, schemas, indent))
        return " | ".join(types)

    if schema_type == "string":
        fmt = schema.get("format", "")
        enum = schema.get("enum")
        if enum:
            return " | ".join(f"'{v}'" for v in enum)
        if fmt in ("date-time", "date"):
            return "string"  # ISO 문자열
        if fmt == "uuid":
            return "string"
        return "string"

    if schema_type == "integer" or schema_type == "number":
        return "number"

    if schema_type == "boolean":
        return "boolean"

    if schema_type == "array":
        items = schema.get("items", {})
        item_type = openapi_type_to_ts(items, schemas, indent)
        return f"{item_type}[]"

    if schema_type == "object":
        additional = schema.get("additionalProperties")
        if additional:
            val_type = openapi_type_to_ts(additional, schemas, indent)
            return f"Record<string, {val_type}>"
        props = schema.get("properties")
        if props:
            return generate_inline_interface(props, schema.get("required", []), schemas, indent)
        return "Record<string, unknown>"

    if schema_type is None and "properties" in schema:
        return generate_inline_interface(
            schema["properties"], schema.get("required", []), schemas, indent,
        )

    return "unknown"


def generate_inline_interface(
    properties: dict, required: list, schemas: dict, indent: int,
) -> str:
    """인라인 객체 타입 생성."""
    pad = "  " * (indent + 1)
    lines = ["{"]
    for name, prop in properties.items():
        optional = "" if name in required else "?"
        ts_type = openapi_type_to_ts(prop, schemas, indent + 1)
        desc = prop.get("description", "")
        if desc:
            lines.append(f"{pad}/** {desc} */")
        lines.append(f"{pad}{name}{optional}: {ts_type};")
    lines.append("  " * indent + "}")
    return "\n".join(lines)


def generate_interface(name: str, schema: dict, schemas: dict) -> str:
    """Pydantic 모델 → TypeScript interface."""
    props = schema.get("properties", {})
    required = schema.get("required", [])
    desc = schema.get("description", "")

    lines = []
    if desc:
        lines.append(f"/** {desc} */")
    lines.append(f"export interface {name} {{")

    for prop_name, prop in props.items():
        optional = "" if prop_name in required else "?"
        ts_type = openapi_type_to_ts(prop, schemas)
        prop_desc = prop.get("description", "")
        if prop_desc:
            lines.append(f"  /** {prop_desc} */")
        lines.append(f"  {prop_name}{optional}: {ts_type};")

    lines.append("}")
    return "\n".join(lines)


def generate_enum(name: str, schema: dict) -> str:
    """enum → TypeScript const + type."""
    values = schema.get("enum", [])
    desc = schema.get("description", "")

    lines = []
    if desc:
        lines.append(f"/** {desc} */")
    lines.append(f"export const {name} = {{")
    for v in values:
        key = v if isinstance(v, str) else str(v)
        lines.append(f"  {key}: '{v}',")
    lines.append("} as const;")
    lines.append(f"export type {name} = (typeof {name})[keyof typeof {name}];")
    return "\n".join(lines)


def generate_types(openapi: dict) -> str:
    """OpenAPI 스키마 전체에서 TypeScript 타입 생성."""
    schemas = openapi.get("components", {}).get("schemas", {})

    lines = [
        "/**",
        " * 자동 생성된 API 타입 — 수동 편집 금지!",
        f" * 생성 시각: {datetime.now().isoformat(timespec='seconds')}",
        f" * OpenAPI 버전: {openapi.get('info', {}).get('version', '?')}",
        " *",
        " * 재생성: npm run generate:types",
        " */",
        "",
        "/* eslint-disable */",
        "",
    ]

    # Enum 먼저 (의존성 순서)
    enums_generated = set()
    for name, schema in sorted(schemas.items()):
        if "enum" in schema:
            lines.append(generate_enum(name, schema))
            lines.append("")
            enums_generated.add(name)

    # 일반 interface
    for name, schema in sorted(schemas.items()):
        if name in enums_generated:
            continue
        if schema.get("type") == "object" or "properties" in schema:
            lines.append(generate_interface(name, schema, schemas))
            lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="OpenAPI → TypeScript 타입 생성")
    parser.add_argument("--url", help="OpenAPI JSON URL (기본: 로컬 앱에서 추출)")
    args = parser.parse_args()

    print("📦 OpenAPI 스키마 로딩...")
    openapi = get_openapi_schema(args.url)
    print(f"   스키마: {len(openapi.get('components', {}).get('schemas', {}))} 타입, "
          f"{len(openapi.get('paths', {}))} 경로")

    print("🔧 TypeScript 타입 생성 중...")
    ts_code = generate_types(openapi)

    SHARED_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(ts_code, encoding="utf-8")
    print(f"✅ 생성 완료: {OUTPUT_FILE}")
    print(f"   {ts_code.count('export interface')} interface + {ts_code.count('export const')} enum")


if __name__ == "__main__":
    main()
