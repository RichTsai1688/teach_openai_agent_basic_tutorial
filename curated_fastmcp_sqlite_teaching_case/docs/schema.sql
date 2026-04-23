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
CREATE TABLE IF NOT EXISTS "case01_sensor_observations" (
            row_id INTEGER PRIMARY KEY,
            "timestamp" TEXT, "pressure_bar" REAL, "discharge_temp_c" REAL, "vibration_mm_s" REAL, "motor_current_a" REAL, "is_injected_anomaly" INTEGER, "anomaly_event_id" TEXT, "anomaly_type" TEXT
        );
CREATE TABLE IF NOT EXISTS "case02_monitoring_observations" (
            row_id INTEGER PRIMARY KEY,
            "timestamp" TEXT, "production_flag" INTEGER, "pressure_bar" REAL, "flow_m3_min" REAL, "power_kw" REAL, "is_injected_anomaly" INTEGER, "anomaly_event_id" TEXT, "anomaly_type" TEXT
        );
CREATE TABLE IF NOT EXISTS "case06_logbook_observations" (
            row_id INTEGER PRIMARY KEY,
            "timestamp" TEXT, "pressure_bar" REAL, "discharge_temp_c" REAL, "power_kw" REAL, "flow_m3_min" REAL, "dryer_dew_point_c" REAL, "is_injected_anomaly" INTEGER, "anomaly_event_id" TEXT, "anomaly_type" TEXT
        );
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
        GROUP BY c.case_id
/* v_case_overview(case_id,title,observation_table,row_count,start_time,end_time,analysis_focus,event_count) */;
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
        ORDER BY start_time
/* v_all_anomaly_events(case_id,event_id,anomaly_type,start_time,end_time,duration_rows,event_score) */;
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
        WHERE is_injected_anomaly = 1
/* v_anomaly_rows(case_id,timestamp,anomaly_event_id,anomaly_type,is_injected_anomaly) */;
