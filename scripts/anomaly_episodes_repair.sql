-- Repair: ensure no closed episode remains active=true
UPDATE anomaly_episodes
SET active = false
WHERE active = true
  AND (end_ts IS NOT NULL OR closed_at IS NOT NULL);

-- Assert: should be 0
SELECT count(*) AS bad_rows
FROM anomaly_episodes
WHERE active = true
  AND (end_ts IS NOT NULL OR closed_at IS NOT NULL);
