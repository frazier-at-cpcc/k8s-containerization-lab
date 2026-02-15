-- Update bucket names before running in Athena.
CREATE DATABASE IF NOT EXISTS lab2_analytics;

CREATE EXTERNAL TABLE IF NOT EXISTS lab2_analytics.hourly_trips (
  pickup_zone STRING,
  hour_of_day INT,
  trip_count BIGINT,
  avg_fare DOUBLE,
  avg_duration_min DOUBLE,
  p90_fare DOUBLE
)
STORED AS PARQUET
LOCATION 's3://dsba6190-yourname-lab2/aggregated/hourly/'
TBLPROPERTIES ('classification'='parquet');

CREATE EXTERNAL TABLE IF NOT EXISTS lab2_analytics.daily_summary (
  pickup_zone STRING,
  total_revenue DOUBLE,
  trip_volume BIGINT
)
PARTITIONED BY (date STRING)
STORED AS PARQUET
LOCATION 's3://dsba6190-yourname-lab2/aggregated/daily_summary/'
TBLPROPERTIES ('classification'='parquet');

MSCK REPAIR TABLE lab2_analytics.daily_summary;

-- Query A: top zones by volume
SELECT pickup_zone, SUM(trip_count) AS total_trips
FROM lab2_analytics.hourly_trips
GROUP BY pickup_zone
ORDER BY total_trips DESC
LIMIT 10;

-- Query B: average fare by hour
SELECT hour_of_day, ROUND(AVG(avg_fare), 2) AS mean_fare
FROM lab2_analytics.hourly_trips
GROUP BY hour_of_day
ORDER BY hour_of_day;

-- Query C1: without partition filter
SELECT pickup_zone, SUM(total_revenue) AS revenue
FROM lab2_analytics.daily_summary
GROUP BY pickup_zone
ORDER BY revenue DESC
LIMIT 5;

-- Query C2: with partition filter
SELECT pickup_zone, SUM(total_revenue) AS revenue
FROM lab2_analytics.daily_summary
WHERE date = '2023-01-15'
GROUP BY pickup_zone
ORDER BY revenue DESC
LIMIT 5;
