-- Case overview: row counts, time ranges, and event counts.
select * from v_case_overview;

-- Injected anomaly row distribution.
select
  case_id,
  anomaly_type,
  count(*) as abnormal_rows
from v_anomaly_rows
group by case_id, anomaly_type
order by case_id, abnormal_rows desc;

-- Event windows from manifests.
select
  case_id,
  event_id,
  anomaly_type,
  start_time,
  end_time,
  event_score
from v_all_anomaly_events
order by start_time;

-- Case 02: production vs non-production flow and power.
select
  production_flag,
  count(*) as rows,
  round(avg(flow_m3_min), 4) as avg_flow_m3_min,
  round(avg(power_kw), 4) as avg_power_kw,
  round(avg(pressure_bar), 4) as avg_pressure_bar
from case02_monitoring_observations
group by production_flag;

-- Case 06: high dew point windows for shift handover.
select
  timestamp,
  dryer_dew_point_c,
  pressure_bar,
  discharge_temp_c,
  power_kw,
  flow_m3_min,
  anomaly_event_id,
  anomaly_type
from case06_logbook_observations
where dryer_dew_point_c >= 7.0
order by timestamp;

-- Recommended FastMCP calls for each selected case.
select
  case_id,
  step_order,
  tool_name,
  arguments_json,
  purpose
from fastmcp_recommended_checks
order by case_id, step_order;

-- FastMCP findings captured while building this teaching case.
select
  case_id,
  tool_name,
  metric,
  finding_text
from fastmcp_findings
order by case_id, finding_id;
