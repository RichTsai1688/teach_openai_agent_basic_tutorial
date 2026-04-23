#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "air_compressor_teaching_cases.sqlite"


CASE_CONFIGS = [
    {
        "case_id": "case_01",
        "title": "Autonomous sensing anomaly diagnosis",
        "observation_table": "case01_sensor_observations",
        "source_csv": "raw_data/case_01_autonomous_sensing/advance/data_case_01_extended.csv",
        "manifest": "raw_data/case_01_autonomous_sensing/advance/data_case_01_extended_manifest.json",
        "analysis_focus": "vibration, discharge temperature, motor current, pressure drift",
        "recommended_checks": [
            {
                "tool": "describe_dataset",
                "arguments": {"time_col": "timestamp"},
                "purpose": "Confirm high-frequency sensor range and missing values.",
            },
            {
                "tool": "baseline_profile",
                "arguments": {"value_col": "vibration_mm_s", "baseline_rows": 24},
                "purpose": "Set the early vibration baseline before scanning drift.",
            },
            {
                "tool": "rolling_anomaly_scan",
                "arguments": {"time_col": "timestamp", "value_col": "vibration_mm_s", "window": 24},
                "purpose": "Find early vibration outliers and injected event windows.",
            },
            {
                "tool": "correlation_report",
                "arguments": {
                    "value_cols": [
                        "vibration_mm_s",
                        "discharge_temp_c",
                        "motor_current_a",
                        "pressure_bar",
                    ]
                },
                "purpose": "Check whether mechanical and electrical signals move together.",
            },
        ],
    },
    {
        "case_id": "case_02",
        "title": "Smart monitoring and night leakage review",
        "observation_table": "case02_monitoring_observations",
        "source_csv": "raw_data/case_02_smart_monitoring/advance/data_case_02_extended.csv",
        "manifest": "raw_data/case_02_smart_monitoring/advance/data_case_02_extended_manifest.json",
        "analysis_focus": "production flag, night flow, power, pressure",
        "recommended_checks": [
            {
                "tool": "describe_dataset",
                "arguments": {"time_col": "timestamp"},
                "purpose": "Confirm day/night coverage and observation count.",
            },
            {
                "tool": "group_compare",
                "arguments": {"group_col": "production_flag", "value_col": "flow_m3_min"},
                "purpose": "Compare flow during production and non-production periods.",
            },
            {
                "tool": "group_compare",
                "arguments": {"group_col": "production_flag", "value_col": "power_kw"},
                "purpose": "Check whether night flow also consumes power.",
            },
            {
                "tool": "correlation_report",
                "arguments": {"value_cols": ["flow_m3_min", "power_kw", "pressure_bar"]},
                "purpose": "Validate whether flow and power are tightly linked.",
            },
        ],
    },
    {
        "case_id": "case_06",
        "title": "Auto logbook and shift handover",
        "observation_table": "case06_logbook_observations",
        "source_csv": "raw_data/case_06_auto_logbook/advance/data_case_06_extended.csv",
        "manifest": "raw_data/case_06_auto_logbook/advance/data_case_06_extended_manifest.json",
        "analysis_focus": "pressure, discharge temperature, power, flow, dryer dew point",
        "recommended_checks": [
            {
                "tool": "describe_dataset",
                "arguments": {"time_col": "timestamp"},
                "purpose": "Confirm logbook coverage and missing values.",
            },
            {
                "tool": "baseline_profile",
                "arguments": {"value_col": "dryer_dew_point_c", "baseline_rows": 24},
                "purpose": "Set dryer dew point baseline for shift handover.",
            },
            {
                "tool": "rolling_anomaly_scan",
                "arguments": {"time_col": "timestamp", "value_col": "dryer_dew_point_c", "window": 24},
                "purpose": "Find dryer issue windows for handover notes.",
            },
            {
                "tool": "correlation_report",
                "arguments": {
                    "value_cols": [
                        "pressure_bar",
                        "discharge_temp_c",
                        "power_kw",
                        "flow_m3_min",
                        "dryer_dew_point_c",
                    ]
                },
                "purpose": "Check which signals explain repeated logbook warnings.",
            },
        ],
    },
]


FASTMCP_FINDINGS = [
    (
        "case_01",
        "describe_dataset",
        "coverage",
        "2160 rows from 2026-05-01 00:00 to 2026-05-15 23:50; no missing sensor values.",
    ),
    (
        "case_01",
        "baseline_profile",
        "vibration_mm_s",
        "First 24-row vibration baseline mean is 2.0722 mm/s, std is 0.0549.",
    ),
    (
        "case_01",
        "rolling_anomaly_scan",
        "vibration_mm_s",
        "73 vibration flags; first rolling flag is 2026-05-01 06:30, with injected event window starting 2026-05-03 12:10.",
    ),
    (
        "case_01",
        "correlation_report",
        "top_pairs",
        "Vibration and discharge temperature correlate at 0.78; discharge temperature and motor current correlate at 0.7686.",
    ),
    (
        "case_02",
        "describe_dataset",
        "coverage",
        "360 hourly rows from 2026-05-01 00:00 to 2026-05-15 23:00; production and non-production periods are balanced.",
    ),
    (
        "case_02",
        "group_compare",
        "flow_m3_min",
        "Mean flow is 1.1164 m3/min when production_flag=0 and 7.7943 m3/min when production_flag=1.",
    ),
    (
        "case_02",
        "group_compare",
        "power_kw",
        "Mean power is 17.329 kW when production_flag=0 and 48.6388 kW when production_flag=1.",
    ),
    (
        "case_02",
        "correlation_report",
        "top_pairs",
        "Flow and power correlate at 0.9982, supporting the night-leak energy-waste framing.",
    ),
    (
        "case_06",
        "describe_dataset",
        "coverage",
        "480 rows from 2026-05-01 08:00 to 2026-05-15 15:45; no missing signal values.",
    ),
    (
        "case_06",
        "baseline_profile",
        "dryer_dew_point_c",
        "First 24-row dryer dew point baseline mean is 3.175 C, std is 0.2129.",
    ),
    (
        "case_06",
        "rolling_anomaly_scan",
        "dryer_dew_point_c",
        "12 dew point flags; notable high dew point windows begin at 2026-05-09 10:00 and 2026-05-13 11:00.",
    ),
    (
        "case_06",
        "correlation_report",
        "top_pairs",
        "Flow and power correlate at 0.9593; discharge temperature also tracks power at 0.6487.",
    ),
]


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        if reader.fieldnames is None:
            raise ValueError(f"No CSV header found: {path}")
        return reader.fieldnames, rows


def infer_sql_type(column: str, rows: list[dict[str, str]]) -> str:
    if column == "timestamp" or column.endswith("_id") or column.endswith("_type"):
        return "TEXT"

    values = [row[column].strip() for row in rows if row.get(column, "").strip()]
    if not values:
        return "TEXT"

    try:
        for value in values:
            int(value)
        return "INTEGER"
    except ValueError:
        pass

    try:
        for value in values:
            float(value)
        return "REAL"
    except ValueError:
        return "TEXT"


def convert_value(value: str, sql_type: str) -> Any:
    value = value.strip()
    if value == "":
        return None
    if sql_type == "INTEGER":
        return int(value)
    if sql_type == "REAL":
        return float(value)
    return value


def quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_observation_table(
    conn: sqlite3.Connection,
    table_name: str,
    csv_path: Path,
) -> dict[str, Any]:
    columns, rows = read_csv_rows(csv_path)
    type_by_column = {column: infer_sql_type(column, rows) for column in columns}

    conn.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
    column_sql = ", ".join(
        f"{quote_identifier(column)} {type_by_column[column]}" for column in columns
    )
    conn.execute(
        f"""
        CREATE TABLE {quote_identifier(table_name)} (
            row_id INTEGER PRIMARY KEY,
            {column_sql}
        )
        """
    )

    placeholders = ", ".join(["?"] * len(columns))
    insert_sql = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(quote_identifier(column) for column in columns)}) "
        f"VALUES ({placeholders})"
    )
    converted_rows = [
        [convert_value(row[column], type_by_column[column]) for column in columns]
        for row in rows
    ]
    conn.executemany(insert_sql, converted_rows)

    timestamps = [row["timestamp"] for row in rows if row.get("timestamp")]
    return {
        "row_count": len(rows),
        "start_time": min(timestamps) if timestamps else None,
        "end_time": max(timestamps) if timestamps else None,
        "columns": columns,
    }


def create_metadata_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP VIEW IF EXISTS v_case_overview;
        DROP VIEW IF EXISTS v_all_anomaly_events;
        DROP VIEW IF EXISTS v_anomaly_rows;
        DROP TABLE IF EXISTS fastmcp_findings;
        DROP TABLE IF EXISTS fastmcp_recommended_checks;
        DROP TABLE IF EXISTS case_events;
        DROP TABLE IF EXISTS cases;

        CREATE TABLE cases (
            case_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            observation_table TEXT NOT NULL,
            source_csv TEXT NOT NULL,
            manifest TEXT NOT NULL,
            row_count INTEGER NOT NULL,
            start_time TEXT,
            end_time TEXT,
            analysis_focus TEXT NOT NULL
        );

        CREATE TABLE case_events (
            case_id TEXT NOT NULL,
            event_id TEXT NOT NULL,
            anomaly_type TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            duration_rows INTEGER,
            strength REAL,
            severity REAL,
            details_json TEXT NOT NULL,
            PRIMARY KEY (case_id, event_id),
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        );

        CREATE TABLE fastmcp_recommended_checks (
            case_id TEXT NOT NULL,
            step_order INTEGER NOT NULL,
            tool_name TEXT NOT NULL,
            arguments_json TEXT NOT NULL,
            purpose TEXT NOT NULL,
            PRIMARY KEY (case_id, step_order),
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        );

        CREATE TABLE fastmcp_findings (
            finding_id INTEGER PRIMARY KEY,
            case_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            metric TEXT NOT NULL,
            finding_text TEXT NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(case_id)
        );
        """
    )


def insert_case_metadata(
    conn: sqlite3.Connection,
    config: dict[str, Any],
    observation_summary: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO cases (
            case_id, title, observation_table, source_csv, manifest,
            row_count, start_time, end_time, analysis_focus
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            config["case_id"],
            config["title"],
            config["observation_table"],
            config["source_csv"],
            config["manifest"],
            observation_summary["row_count"],
            observation_summary["start_time"],
            observation_summary["end_time"],
            config["analysis_focus"],
        ),
    )

    for index, check in enumerate(config["recommended_checks"], start=1):
        arguments = dict(check["arguments"])
        arguments.setdefault("csv_path", config["source_csv"])
        conn.execute(
            """
            INSERT INTO fastmcp_recommended_checks (
                case_id, step_order, tool_name, arguments_json, purpose
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                config["case_id"],
                index,
                check["tool"],
                json.dumps(arguments, ensure_ascii=False, sort_keys=True),
                check["purpose"],
            ),
        )


def insert_manifest_events(
    conn: sqlite3.Connection,
    case_id: str,
    manifest_path: Path,
) -> None:
    manifest = load_manifest(manifest_path)
    for event in manifest.get("events", []):
        conn.execute(
            """
            INSERT INTO case_events (
                case_id, event_id, anomaly_type, start_time, end_time,
                duration_rows, strength, severity, details_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                event.get("event_id", ""),
                event.get("anomaly_type", ""),
                event.get("start_time"),
                event.get("end_time"),
                event.get("duration_rows"),
                event.get("strength"),
                event.get("severity"),
                json.dumps(event, ensure_ascii=False, sort_keys=True),
            ),
        )


def insert_fastmcp_findings(conn: sqlite3.Connection) -> None:
    conn.executemany(
        """
        INSERT INTO fastmcp_findings (case_id, tool_name, metric, finding_text)
        VALUES (?, ?, ?, ?)
        """,
        FASTMCP_FINDINGS,
    )


def create_views(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE VIEW v_case_overview AS
        SELECT
            c.case_id,
            c.title,
            c.observation_table,
            c.row_count,
            c.start_time,
            c.end_time,
            c.analysis_focus,
            COUNT(e.event_id) AS event_count
        FROM cases c
        LEFT JOIN case_events e ON e.case_id = c.case_id
        GROUP BY c.case_id;

        CREATE VIEW v_all_anomaly_events AS
        SELECT
            case_id,
            event_id,
            anomaly_type,
            start_time,
            end_time,
            COALESCE(duration_rows, 0) AS duration_rows,
            COALESCE(strength, severity, 0.0) AS event_score
        FROM case_events
        ORDER BY start_time;

        CREATE VIEW v_anomaly_rows AS
        SELECT
            'case_01' AS case_id,
            timestamp,
            anomaly_event_id,
            anomaly_type,
            is_injected_anomaly
        FROM case01_sensor_observations
        WHERE is_injected_anomaly = 1
        UNION ALL
        SELECT
            'case_02' AS case_id,
            timestamp,
            anomaly_event_id,
            anomaly_type,
            is_injected_anomaly
        FROM case02_monitoring_observations
        WHERE is_injected_anomaly = 1
        UNION ALL
        SELECT
            'case_06' AS case_id,
            timestamp,
            anomaly_event_id,
            anomaly_type,
            is_injected_anomaly
        FROM case06_logbook_observations
        WHERE is_injected_anomaly = 1;
        """
    )


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        create_metadata_tables(conn)

        for config in CASE_CONFIGS:
            csv_path = ROOT / config["source_csv"]
            manifest_path = ROOT / config["manifest"]
            summary = load_observation_table(conn, config["observation_table"], csv_path)
            insert_case_metadata(conn, config, summary)
            insert_manifest_events(conn, config["case_id"], manifest_path)

        insert_fastmcp_findings(conn)
        create_views(conn)
        conn.execute("VACUUM")

    print(f"Built SQLite database: {DB_PATH}")


if __name__ == "__main__":
    main()
