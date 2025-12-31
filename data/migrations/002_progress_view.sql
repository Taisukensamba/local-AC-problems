CREATE VIEW IF NOT EXISTS progress AS
SELECT
    p.problem_id,
    p.contest_id,
    p.task_index,
    p.title,
    p.point,
    p.url,
    p.difficulty,
    s.user_id,
    CASE WHEN SUM(CASE WHEN s.result = 'AC' THEN 1 ELSE 0 END) > 0 THEN 1 ELSE 0 END AS is_ac,
    MIN(CASE WHEN s.result = 'AC' THEN s.epoch_second END) AS first_ac_epoch,
    MAX(s.epoch_second) AS last_submit_epoch,
    SUM(CASE WHEN s.result = 'AC' THEN 1 ELSE 0 END) AS ac_count,
    SUM(CASE WHEN s.result IS NOT NULL AND s.result != 'AC' THEN 1 ELSE 0 END) AS not_ac_count
FROM problems p
LEFT JOIN submissions s ON s.problem_id = p.problem_id
GROUP BY p.problem_id, s.user_id;
