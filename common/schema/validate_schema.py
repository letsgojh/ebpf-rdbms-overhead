#!/usr/bin/env python3
"""common/schema/validate_schema.py

results/<group>/*.csv 를 result_schema.json에 대해 검증한다.
results_aggregated/ 로 옮기기 전에 반드시 이 스크립트를 통과해야 한다
(README "결과 스키마 규칙" 절 참고).

사용법:
    python common/schema/validate_schema.py systems/duckdb/results/group_a/duckdb_fentry_na_na_run000.csv
    python common/schema/validate_schema.py systems/*/results/**/*.csv   # 여러 파일/glob도 가능
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import jsonschema

SCHEMA_PATH = Path(__file__).parent / "result_schema.json"

# 0.2 파일명 규칙: <system>_<probe_type>_<sf 또는 na>_<probe_location 또는 na>_run<NN>.csv
# probe_type에 언더스코어가 들어가는 경우(raw_tracepoint)가 있어 [a-z_]+로 허용한다 — 뒤쪽
# sf/probe_location/run<NN> 앵커가 있어서 정규식 백트래킹으로 여전히 올바르게 갈린다.
FILENAME_RE = re.compile(
    r"^(?P<system>[a-z]+)_(?P<probe_type>[a-z_]+)_(?P<sf>sf\d+|na)_"
    r"(?P<probe_location>[a-z]+|na)_run(?P<run_id>\d+)\.csv$"
)


def load_schema(schema_path: Path = SCHEMA_PATH) -> dict:
    with schema_path.open(encoding="utf-8") as f:
        return json.load(f)


def _expected_type(prop_schema: dict) -> set[str]:
    t = prop_schema.get("type", [])
    return {t} if isinstance(t, str) else set(t)


def coerce_row(row: dict[str, str], schema: dict) -> dict:
    """csv.DictReader가 만든 문자열 dict를 스키마 타입에 맞게 변환한다.
    빈 문자열은 null(None)로, integer/number 컬럼은 int/float로 캐스팅한다.
    알 수 없는(스키마에 없는) 컬럼은 문자열 그대로 통과시킨다."""
    props = schema.get("properties", {})
    out = {}
    for key, raw in row.items():
        if key is None:
            continue  # DictReader가 헤더보다 많은 열을 None 키에 몰아넣는 경우
        prop_schema = props.get(key)
        if raw == "" or raw is None:
            out[key] = None
            continue
        if prop_schema is None:
            out[key] = raw
            continue
        types = _expected_type(prop_schema)
        try:
            if "integer" in types:
                out[key] = int(raw)
            elif "number" in types:
                out[key] = float(raw)
            else:
                out[key] = raw
        except ValueError:
            out[key] = raw  # 캐스팅 실패는 그대로 두고 jsonschema가 타입 오류로 잡게 함
    return out


def check_filename(path: Path) -> list[str]:
    """0.2 파일명 규칙 위반을 warning 문자열 리스트로 반환한다(하드 실패 아님)."""
    warnings = []
    if not FILENAME_RE.match(path.name):
        warnings.append(
            f"파일명이 명명 규칙과 다름: {path.name} "
            f"(기대 형식: <system>_<probe_type>_<sf|na>_<probe_location|na>_run<NN>.csv)"
        )
    return warnings


def validate_file(path: Path, schema: dict, validator: jsonschema.protocols.Validator) -> tuple[list[str], list[str]]:
    """(errors, warnings) 반환. errors가 비어있어야 통과."""
    errors: list[str] = []
    warnings = check_filename(path)

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            errors.append("헤더가 없는(빈) CSV")
            return errors, warnings

        unknown_cols = set(reader.fieldnames) - set(schema.get("properties", {}))
        if unknown_cols:
            warnings.append(f"스키마에 없는 컬럼(오타 의심): {sorted(unknown_cols)}")

        row_count = 0
        for line_no, row in enumerate(reader, start=2):  # 헤더가 1행
            row_count += 1
            instance = coerce_row(row, schema)
            for err in validator.iter_errors(instance):
                loc = "/".join(str(p) for p in err.path) or "(row 전체)"
                errors.append(f"{path.name}:{line_no}: [{loc}] {err.message}")

        if row_count == 0:
            warnings.append("데이터 행이 하나도 없음(헤더만 존재)")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_files", nargs="+", help="검증할 CSV 파일 경로(들)")
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH, help="사용할 JSON schema 경로(기본: 같은 디렉토리의 result_schema.json)")
    args = parser.parse_args()

    schema = load_schema(args.schema)
    validator = jsonschema.Draft7Validator(schema)

    total_errors = 0
    for raw_path in args.csv_files:
        path = Path(raw_path)
        if not path.is_file():
            print(f"[SKIP] 파일 없음: {path}", file=sys.stderr)
            total_errors += 1
            continue

        errors, warnings = validate_file(path, schema, validator)
        for w in warnings:
            print(f"[WARN] {path.name}: {w}")
        if errors:
            print(f"[FAIL] {path} — {len(errors)}건 오류")
            for e in errors:
                print(f"  - {e}")
            total_errors += len(errors)
        else:
            print(f"[OK]   {path}")

    return 1 if total_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
