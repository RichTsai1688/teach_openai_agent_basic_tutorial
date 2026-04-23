from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
from fastmcp import FastMCP

mcp = FastMCP("AirCompressorStats")

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PACKAGE_ROOT / "data" / "air_compressor_teaching_cases.sqlite"
RAW_DATA_ROOT = PACKAGE_ROOT / "raw_data"
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CASE_ALIASES = {
    "case_3": "case_06",
    "case_03": "case_06",
    "task_3": "case_06",
    "task_03": "case_06",
    "handover": "case_06",
    "shift_handover": "case_06",
}


def _normalize_case_id(case_id: str) -> str:
    normalized = case_id.strip().lower()
    return CASE_ALIASES.get(normalized, normalized)


def _round_float(value: Any, digits: int = 4) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def _resolve_db_path(db_path: str = "") -> Path:
    configured = db_path.strip() or os.getenv("AIR_COMPRESSOR_DB_PATH", "").strip()
    if configured:
        raw_path = Path(configured).expanduser()
        candidates = [raw_path] if raw_path.is_absolute() else [PACKAGE_ROOT / raw_path, Path.cwd() / raw_path]
    else:
        candidates = [DEFAULT_DB_PATH]

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _connect(db_path: str = "") -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Unsafe SQLite identifier: {identifier}")
    return f'"{identifier}"'


def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _json_loads(value: Any) -> Any:
    if value in (None, ""):
        return None
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _get_case_info(conn: sqlite3.Connection, case_id: str) -> dict[str, Any]:
    normalized = _normalize_case_id(case_id)
    row = conn.execute(
        """
        SELECT case_id, title, observation_table, source_csv, manifest, row_count,
               start_time, end_time, analysis_focus
        FROM cases
        WHERE case_id = ?
        """,
        (normalized,),
    ).fetchone()
    if row is None:
        available = [
            item["case_id"]
            for item in _rows_to_dicts(conn.execute("SELECT case_id FROM cases ORDER BY case_id").fetchall())
        ]
        raise ValueError(f"Unknown case_id: {case_id}. Available cases: {available}")
    return dict(row)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _load_case_dataframe(case_id: str, db_path: str = "") -> tuple[dict[str, Any], pd.DataFrame]:
    with _connect(db_path) as conn:
        case_info = _get_case_info(conn, case_id)
        table_name = str(case_info["observation_table"])
        if not _table_exists(conn, table_name):
            raise ValueError(f"Observation table does not exist: {table_name}")
        quoted_table = _quote_identifier(table_name)
        df = pd.read_sql_query(f"SELECT * FROM {quoted_table} ORDER BY row_id", conn)
    return case_info, df


def _load_csv(csv_path: str) -> pd.DataFrame:
    raw_path = Path(csv_path).expanduser()
    candidates = [raw_path] if raw_path.is_absolute() else [
        Path.cwd() / raw_path,
        PACKAGE_ROOT / raw_path,
        RAW_DATA_ROOT / raw_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return pd.read_csv(candidate.resolve(), encoding="utf-8-sig")
    raise FileNotFoundError(f"CSV not found: {csv_path}")


def _describe_dataframe(df: pd.DataFrame, time_col: str = "timestamp") -> dict[str, Any]:
    result: dict[str, Any] = {
        "rows": int(len(df)),
        "columns": list(df.columns),
        "missing_by_column": {column: int(value) for column, value in df.isna().sum().to_dict().items()},
    }
    if time_col in df.columns:
        time_series = pd.to_datetime(df[time_col], errors="coerce")
        if time_series.notna().any():
            result["time_range"] = {
                "start": time_series.min().strftime("%Y-%m-%d %H:%M"),
                "end": time_series.max().strftime("%Y-%m-%d %H:%M"),
            }
            result["period_count"] = int(time_series.notna().sum())
    return result


def _baseline_profile_dataframe(df: pd.DataFrame, value_col: str, baseline_rows: int = 24) -> dict[str, Any]:
    if value_col not in df.columns:
        raise ValueError(f"Unknown value_col: {value_col}")
    series = pd.to_numeric(df[value_col], errors="coerce").dropna().head(max(1, int(baseline_rows)))
    if series.empty:
        return {
            "value_col": value_col,
            "baseline_rows": 0,
            "warning": "No numeric values available for baseline.",
        }

    q1 = float(series.quantile(0.25))
    q3 = float(series.quantile(0.75))
    median = float(series.median())
    mad = float((series - median).abs().median())
    return {
        "value_col": value_col,
        "baseline_rows": int(len(series)),
        "mean": _round_float(series.mean()),
        "std": _round_float(series.std(ddof=0)),
        "median": _round_float(median),
        "mad": _round_float(mad),
        "iqr": _round_float(q3 - q1),
        "min": _round_float(series.min()),
        "max": _round_float(series.max()),
    }


def _rolling_anomaly_scan_dataframe(
    df: pd.DataFrame,
    time_col: str,
    value_col: str,
    window: int = 24,
    z_threshold: float = 2.5,
) -> dict[str, Any]:
    if time_col not in df.columns:
        raise ValueError(f"Unknown time_col: {time_col}")
    if value_col not in df.columns:
        raise ValueError(f"Unknown value_col: {value_col}")

    working = df[[time_col, value_col]].copy()
    working[time_col] = pd.to_datetime(working[time_col], errors="coerce")
    working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
    working = working.dropna().sort_values(time_col).reset_index(drop=True)
    if working.empty:
        return {
            "value_col": value_col,
            "window": int(window),
            "z_threshold": float(z_threshold),
            "flag_count": 0,
            "first_flag": None,
            "top_flags": [],
            "warning": "No numeric time-series values available for anomaly scan.",
        }

    window = max(2, int(window))
    min_periods = min(len(working), max(5, window // 3))
    rolling_mean = working[value_col].rolling(window=window, min_periods=min_periods).mean()
    rolling_std = working[value_col].rolling(window=window, min_periods=min_periods).std(ddof=0)
    nonzero_std = rolling_std.mask(rolling_std == 0)
    fallback_std = nonzero_std.dropna().median()
    if pd.isna(fallback_std) or float(fallback_std) == 0:
        fallback_std = 1.0
    safe_std = nonzero_std.fillna(float(fallback_std))
    z_score = ((working[value_col] - rolling_mean) / safe_std).fillna(0)
    mask = z_score.abs() >= float(z_threshold)
    flagged = working.loc[mask, [time_col, value_col]].copy()
    flagged["z_score"] = z_score[mask].round(3).values

    return {
        "value_col": value_col,
        "window": window,
        "z_threshold": float(z_threshold),
        "flag_count": int(len(flagged)),
        "first_flag": None if flagged.empty else flagged.iloc[0][time_col].strftime("%Y-%m-%d %H:%M"),
        "top_flags": [
            {
                "timestamp": row[time_col].strftime("%Y-%m-%d %H:%M"),
                "value": _round_float(row[value_col]),
                "z_score": _round_float(row["z_score"], 3),
            }
            for _, row in flagged.head(10).iterrows()
        ],
    }


def _group_compare_dataframe(df: pd.DataFrame, group_col: str, value_col: str) -> dict[str, Any]:
    if group_col not in df.columns:
        raise ValueError(f"Unknown group_col: {group_col}")
    if value_col not in df.columns:
        raise ValueError(f"Unknown value_col: {value_col}")

    working = df[[group_col, value_col]].copy()
    working[value_col] = pd.to_numeric(working[value_col], errors="coerce")
    working = working.dropna(subset=[value_col])
    grouped = (
        working.groupby(group_col)[value_col]
        .agg(["count", "mean", "median", "std", "min", "max"])
        .reset_index()
    )
    result = []
    for row in grouped.itertuples(index=False):
        result.append(
            {
                group_col: row[0],
                "count": int(row.count),
                "mean": _round_float(row.mean),
                "median": _round_float(row.median),
                "std": _round_float(0.0 if pd.isna(row.std) else row.std),
                "min": _round_float(row.min),
                "max": _round_float(row.max),
            }
        )
    return {"group_col": group_col, "value_col": value_col, "groups": result}


def _correlation_report_dataframe(df: pd.DataFrame, value_cols: list[str]) -> dict[str, Any]:
    missing = [column for column in value_cols if column not in df.columns]
    if missing:
        raise ValueError(f"Unknown value_cols: {missing}")

    working = df[value_cols].apply(pd.to_numeric, errors="coerce")
    corr = working.corr().fillna(0.0)
    pairs = []
    for left_index, left in enumerate(value_cols):
        for right in value_cols[left_index + 1 :]:
            pairs.append(
                {
                    "pair": f"{left} vs {right}",
                    "corr": _round_float(corr.loc[left, right]),
                }
            )
    pairs.sort(key=lambda item: abs(float(item["corr"] or 0)), reverse=True)
    return {
        "value_cols": value_cols,
        "matrix": {
            column: {inner: _round_float(value) for inner, value in corr[column].items()}
            for column in corr.columns
        },
        "top_pairs": pairs[:10],
    }


def _case_events(case_id: str, db_path: str = "") -> list[dict[str, Any]]:
    normalized = _normalize_case_id(case_id)
    with _connect(db_path) as conn:
        _get_case_info(conn, normalized)
        rows = conn.execute(
            """
            SELECT case_id, event_id, anomaly_type, start_time, end_time,
                   duration_rows, strength, severity, details_json
            FROM case_events
            WHERE case_id = ?
            ORDER BY start_time, event_id
            """,
            (normalized,),
        ).fetchall()
    events = _rows_to_dicts(rows)
    for event in events:
        event["details"] = _json_loads(event.pop("details_json", None))
    return events


def _case_findings(case_id: str, db_path: str = "") -> list[dict[str, Any]]:
    normalized = _normalize_case_id(case_id)
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT finding_id, case_id, tool_name, metric, finding_text
            FROM fastmcp_findings
            WHERE case_id = ?
            ORDER BY finding_id
            """,
            (normalized,),
        ).fetchall()
    return _rows_to_dicts(rows)


def _first_event_time(events: list[dict[str, Any]]) -> str | None:
    starts = [str(event["start_time"]) for event in events if event.get("start_time")]
    return min(starts) if starts else None


def _event_counts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(event["anomaly_type"]) for event in events if event.get("anomaly_type"))
    return [{"anomaly_type": name, "count": count} for name, count in counts.most_common()]


def _group_lookup(group_compare_result: dict[str, Any], group_col: str, key: Any) -> dict[str, Any] | None:
    for group in group_compare_result.get("groups", []):
        if str(group.get(group_col)) == str(key):
            return group
    return None


@mcp.tool
def describe_dataset(csv_path: str, time_col: str = "timestamp") -> dict[str, Any]:
    """Describe a CSV dataset: rows, columns, missing values, and time range."""
    df = _load_csv(csv_path)
    return _describe_dataframe(df, time_col)


@mcp.tool
def baseline_profile(csv_path: str, value_col: str, baseline_rows: int = 24) -> dict[str, Any]:
    """Return baseline statistics for the first N rows of a numeric CSV column."""
    df = _load_csv(csv_path)
    return _baseline_profile_dataframe(df, value_col, baseline_rows)


@mcp.tool
def rolling_anomaly_scan(
    csv_path: str,
    time_col: str,
    value_col: str,
    window: int = 24,
    z_threshold: float = 2.5,
) -> dict[str, Any]:
    """Scan a CSV time series with rolling mean/std and report z-score anomalies."""
    df = _load_csv(csv_path)
    return _rolling_anomaly_scan_dataframe(df, time_col, value_col, window, z_threshold)


@mcp.tool
def group_compare(csv_path: str, group_col: str, value_col: str) -> dict[str, Any]:
    """Compare mean, median, std, and counts across groups in a CSV dataset."""
    df = _load_csv(csv_path)
    return _group_compare_dataframe(df, group_col, value_col)


@mcp.tool
def correlation_report(csv_path: str, value_cols: list[str]) -> dict[str, Any]:
    """Return a correlation matrix for selected numeric CSV columns."""
    df = _load_csv(csv_path)
    return _correlation_report_dataframe(df, value_cols)


@mcp.tool
def database_health(db_path: str = "") -> dict[str, Any]:
    """Check whether the SQLite teaching database is reachable and ready."""
    path = _resolve_db_path(db_path)
    result: dict[str, Any] = {
        "db_path": str(path),
        "exists": path.exists(),
        "ready": False,
        "cases": [],
        "errors": [],
    }
    if not path.exists():
        result["errors"].append("SQLite database file does not exist.")
        return result

    try:
        with _connect(str(path)) as conn:
            case_rows = conn.execute(
                """
                SELECT case_id, title, observation_table, row_count, start_time, end_time
                FROM cases
                ORDER BY case_id
                """
            ).fetchall()
            cases = []
            for row in _rows_to_dicts(case_rows):
                table_name = str(row["observation_table"])
                actual_rows = None
                table_ready = _table_exists(conn, table_name)
                if table_ready:
                    actual_rows = conn.execute(
                        f"SELECT COUNT(*) AS count FROM {_quote_identifier(table_name)}"
                    ).fetchone()["count"]
                cases.append(
                    {
                        **row,
                        "table_exists": table_ready,
                        "actual_rows": int(actual_rows) if actual_rows is not None else None,
                        "row_count_matches": actual_rows == row["row_count"],
                    }
                )
            result["cases"] = cases
            result["case_count"] = len(cases)
            result["ready"] = bool(cases) and all(
                item["table_exists"] and item["row_count_matches"] for item in cases
            )
    except Exception as exc:  # pragma: no cover - returned to the agent for diagnosis
        result["errors"].append(str(exc))
    return result


@mcp.tool
def list_cases(db_path: str = "") -> dict[str, Any]:
    """List available SQLite teaching cases."""
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT case_id, title, observation_table, row_count, start_time, end_time, analysis_focus
            FROM cases
            ORDER BY case_id
            """
        ).fetchall()
    return {"cases": _rows_to_dicts(rows), "aliases": CASE_ALIASES}


@mcp.tool
def get_case_overview(case_id: str, db_path: str = "") -> dict[str, Any]:
    """Return metadata and overview for one teaching case."""
    normalized = _normalize_case_id(case_id)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM v_case_overview WHERE case_id = ?", (normalized,)).fetchone()
        if row is None:
            _get_case_info(conn, normalized)
    return dict(row) if row is not None else {}


@mcp.tool
def get_recommended_checks(case_id: str, db_path: str = "") -> dict[str, Any]:
    """Return the recommended FastMCP tool sequence for a case."""
    normalized = _normalize_case_id(case_id)
    with _connect(db_path) as conn:
        _get_case_info(conn, normalized)
        rows = conn.execute(
            """
            SELECT case_id, step_order, tool_name, arguments_json, purpose
            FROM fastmcp_recommended_checks
            WHERE case_id = ?
            ORDER BY step_order
            """,
            (normalized,),
        ).fetchall()
    checks = _rows_to_dicts(rows)
    for check in checks:
        check["arguments"] = _json_loads(check.pop("arguments_json", None))
    return {"case_id": normalized, "recommended_checks": checks}


@mcp.tool
def get_case_events(case_id: str, db_path: str = "") -> dict[str, Any]:
    """Return known injected or curated anomaly events for a case."""
    normalized = _normalize_case_id(case_id)
    events = _case_events(normalized, db_path)
    return {
        "case_id": normalized,
        "event_count": len(events),
        "first_event": _first_event_time(events),
        "event_type_counts": _event_counts(events),
        "events": events,
    }


@mcp.tool
def describe_case(case_id: str, time_col: str = "timestamp", db_path: str = "") -> dict[str, Any]:
    """Describe a SQLite teaching case: rows, columns, missing values, and time range."""
    case_info, df = _load_case_dataframe(case_id, db_path)
    result = _describe_dataframe(df, time_col)
    return {"case_id": case_info["case_id"], "case_title": case_info["title"], **result}


@mcp.tool
def baseline_profile_case(
    case_id: str,
    value_col: str,
    baseline_rows: int = 24,
    db_path: str = "",
) -> dict[str, Any]:
    """Return baseline statistics for the first N rows of a SQLite case column."""
    case_info, df = _load_case_dataframe(case_id, db_path)
    result = _baseline_profile_dataframe(df, value_col, baseline_rows)
    return {"case_id": case_info["case_id"], **result}


@mcp.tool
def rolling_anomaly_scan_case(
    case_id: str,
    time_col: str,
    value_col: str,
    window: int = 24,
    z_threshold: float = 2.5,
    db_path: str = "",
) -> dict[str, Any]:
    """Scan a SQLite case time series with rolling mean/std and report z-score anomalies."""
    case_info, df = _load_case_dataframe(case_id, db_path)
    result = _rolling_anomaly_scan_dataframe(df, time_col, value_col, window, z_threshold)
    return {"case_id": case_info["case_id"], **result}


@mcp.tool
def group_compare_case(
    case_id: str,
    group_col: str,
    value_col: str,
    db_path: str = "",
) -> dict[str, Any]:
    """Compare mean, median, std, and counts across groups in a SQLite case."""
    case_info, df = _load_case_dataframe(case_id, db_path)
    result = _group_compare_dataframe(df, group_col, value_col)
    return {"case_id": case_info["case_id"], **result}


@mcp.tool
def correlation_report_case(case_id: str, value_cols: list[str], db_path: str = "") -> dict[str, Any]:
    """Return a correlation matrix for selected numeric columns in a SQLite case."""
    case_info, df = _load_case_dataframe(case_id, db_path)
    result = _correlation_report_dataframe(df, value_cols)
    return {"case_id": case_info["case_id"], **result}


@mcp.tool
def analyze_autonomous_sensing(case_id: str = "case_01", db_path: str = "") -> dict[str, Any]:
    """Analyze Case 01 autonomous sensing anomalies with the recommended statistical flow."""
    normalized = _normalize_case_id(case_id)
    case_info, df = _load_case_dataframe(normalized, db_path)
    value_cols = ["vibration_mm_s", "discharge_temp_c", "motor_current_a", "pressure_bar"]
    description = _describe_dataframe(df)
    baselines = {
        column: _baseline_profile_dataframe(df, column, 24)
        for column in value_cols
        if column in df.columns
    }
    scans = {
        column: _rolling_anomaly_scan_dataframe(df, "timestamp", column, 24, 2.5)
        for column in ["vibration_mm_s", "discharge_temp_c"]
        if column in df.columns
    }
    correlation = _correlation_report_dataframe(df, value_cols)
    events = _case_events(normalized, db_path)
    findings = _case_findings(normalized, db_path)

    first_stat_flag = min(
        [scan["first_flag"] for scan in scans.values() if scan.get("first_flag")],
        default=None,
    )
    first_event = _first_event_time(events)
    status = "abnormal" if events or any(scan["flag_count"] for scan in scans.values()) else "normal"
    top_pair = correlation["top_pairs"][0] if correlation["top_pairs"] else None
    summary = (
        f"異常狀態：{('異常，需追查' if status == 'abnormal' else '目前未見明顯異常')}。"
        f"最早統計旗標為 {first_stat_flag or '無'}，已知事件最早從 {first_event or '無'} 開始。"
        f"振動與排氣溫度是優先訊號，{top_pair['pair']} 相關係數為 {top_pair['corr']}。"
        "建議先檢查軸承、潤滑與冷卻條件，再比對馬達電流與壓力是否同步偏移。"
    )
    return {
        "case_id": case_info["case_id"],
        "case_title": case_info["title"],
        "scenario": "autonomous_sensing",
        "status": status,
        "summary": summary,
        "evidence": {
            "description": description,
            "baselines": baselines,
            "rolling_scans": scans,
            "correlation": correlation,
            "event_count": len(events),
            "first_event": first_event,
            "event_type_counts": _event_counts(events),
            "findings": findings,
        },
        "suggested_next_actions": [
            "先檢查振動升高時段的軸承與潤滑狀態。",
            "比對排氣溫度與馬達電流是否同步升高。",
            "回看同時段壓力是否有下滑或負載突變。",
        ],
    }


@mcp.tool
def analyze_night_leakage(case_id: str = "case_02", db_path: str = "") -> dict[str, Any]:
    """Analyze Case 02 production/non-production differences and night leakage risk."""
    normalized = _normalize_case_id(case_id)
    case_info, df = _load_case_dataframe(normalized, db_path)
    description = _describe_dataframe(df)
    flow_compare = _group_compare_dataframe(df, "production_flag", "flow_m3_min")
    power_compare = _group_compare_dataframe(df, "production_flag", "power_kw")
    flow_scan = _rolling_anomaly_scan_dataframe(df, "timestamp", "flow_m3_min", 12, 2.0)
    correlation = _correlation_report_dataframe(df, ["flow_m3_min", "power_kw", "pressure_bar"])
    events = _case_events(normalized, db_path)
    findings = _case_findings(normalized, db_path)

    non_production_flow = _group_lookup(flow_compare, "production_flag", 0)
    production_flow = _group_lookup(flow_compare, "production_flag", 1)
    non_production_power = _group_lookup(power_compare, "production_flag", 0)
    first_event = _first_event_time(events)
    flow_power_corr = next(
        (pair["corr"] for pair in correlation["top_pairs"] if pair["pair"] == "flow_m3_min vs power_kw"),
        None,
    )
    non_prod_flow_mean = float(non_production_flow["mean"]) if non_production_flow else 0.0
    status = "suspected_night_leakage" if events or non_prod_flow_mean > 1.0 else "normal"
    summary = (
        f"夜間漏氣判斷：{('疑似存在夜間漏氣或非生產用氣' if status != 'normal' else '目前未見明顯夜間漏氣')}。"
        f"非生產平均流量為 {non_production_flow['mean'] if non_production_flow else '無資料'} m3/min，"
        f"生產平均流量為 {production_flow['mean'] if production_flow else '無資料'} m3/min。"
        f"非生產平均功率為 {non_production_power['mean'] if non_production_power else '無資料'} kW，"
        f"流量與功率相關係數為 {flow_power_corr}。"
        f"已知夜間漏氣事件最早從 {first_event or '無'} 開始，建議安排夜間分區隔離與漏氣巡檢。"
    )
    return {
        "case_id": case_info["case_id"],
        "case_title": case_info["title"],
        "scenario": "night_leakage",
        "status": status,
        "summary": summary,
        "evidence": {
            "description": description,
            "flow_compare": flow_compare,
            "power_compare": power_compare,
            "flow_scan": flow_scan,
            "correlation": correlation,
            "event_count": len(events),
            "first_event": first_event,
            "event_type_counts": _event_counts(events),
            "findings": findings,
        },
        "suggested_next_actions": [
            "先在非生產時段做分區隔離，確認哪一段流量仍偏高。",
            "比對夜間功率是否隨流量同步升高，估算浪費電力。",
            "排除合法夜間用氣後，再安排超音波測漏與修復驗證。",
        ],
    }


@mcp.tool
def build_shift_handover(case_id: str = "case_06", db_path: str = "") -> dict[str, Any]:
    """Build a shift handover summary from repeated anomalies in the logbook case."""
    normalized = _normalize_case_id(case_id)
    case_info, df = _load_case_dataframe(normalized, db_path)
    description = _describe_dataframe(df)
    scans = {
        column: _rolling_anomaly_scan_dataframe(df, "timestamp", column, 24, 2.5)
        for column in ["pressure_bar", "discharge_temp_c", "dryer_dew_point_c"]
        if column in df.columns
    }
    correlation = _correlation_report_dataframe(
        df,
        ["pressure_bar", "discharge_temp_c", "power_kw", "flow_m3_min", "dryer_dew_point_c"],
    )
    events = _case_events(normalized, db_path)
    findings = _case_findings(normalized, db_path)
    counts = _event_counts(events)
    first_event = _first_event_time(events)
    repeated = [item for item in counts if item["count"] >= 2]
    priority_windows = [
        {
            "event_id": event["event_id"],
            "anomaly_type": event["anomaly_type"],
            "start_time": event["start_time"],
            "end_time": event["end_time"],
            "score": event.get("severity") or event.get("strength"),
        }
        for event in events[:8]
    ]
    status = "handover_required" if repeated else "monitor"
    repeated_text = "、".join(f"{item['anomaly_type']} {item['count']} 次" for item in repeated) or "無明顯重複"
    summary = (
        f"交班狀態：{('需列入交班追蹤' if status == 'handover_required' else '可持續觀察')}。"
        f"最早異常從 {first_event or '無'} 開始，重複模式為 {repeated_text}。"
        "低壓、冷卻異常與乾燥機露點偏高需分別追查，"
        "交班時應標明已發生時段、目前狀態與下一班需確認的檢查項目。"
    )
    return {
        "case_id": case_info["case_id"],
        "case_title": case_info["title"],
        "scenario": "shift_handover",
        "status": status,
        "summary": summary,
        "evidence": {
            "description": description,
            "rolling_scans": scans,
            "correlation": correlation,
            "event_count": len(events),
            "first_event": first_event,
            "event_type_counts": counts,
            "priority_windows": priority_windows,
            "findings": findings,
        },
        "suggested_next_actions": [
            "將低壓、冷卻異常、乾燥機露點偏高分成三條交班追蹤項。",
            "下一班先確認最近一次異常是否已恢復到基準範圍。",
            "若同類異常再次出現，升級為維修派工或分區檢查。",
        ],
    }


if __name__ == "__main__":
    mcp.run()
