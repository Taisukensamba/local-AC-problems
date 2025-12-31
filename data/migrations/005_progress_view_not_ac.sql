DROP VIEW IF EXISTS progress;

CREATE VIEW IF NOT EXISTS progress AS
SELECT
    p.problem_uid,
    p.oj,
    p.contest_uid,
    p.contest_id,
    p.task_index,
    p.title,
    p.point,
    p.url,
    p.difficulty,
    s.user_id,
    CASE WHEN SUM(CASE WHEN s.result IN ('AC', 'OK') THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END AS is_ac,
    MIN(CASE WHEN s.result IN ('AC', 'OK') THEN s.epoch_second END) AS first_ac_epoch,
    MAX(s.epoch_second) AS last_submit_epoch,
    SUM(CASE WHEN s.result IN ('AC', 'OK') THEN 1 ELSE 0 END) AS ac_count,
    SUM(CASE WHEN s.result IS NOT NULL AND s.result NOT IN ('AC', 'OK') THEN 1 ELSE 0 END) AS not_ac_count
FROM problems p
LEFT JOIN submissions s ON s.problem_uid = p.problem_uid
GROUP BY p.problem_uid, s.user_id;

PRAGMA user_version = 6;
