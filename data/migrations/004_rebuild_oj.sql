PRAGMA foreign_keys = OFF;

DROP VIEW IF EXISTS progress;
DROP TABLE IF EXISTS problem_tags;
DROP TABLE IF EXISTS submissions;
DROP TABLE IF EXISTS problems;
DROP TABLE IF EXISTS contests;
DROP TABLE IF EXISTS sync_state;

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS contests (
    contest_uid TEXT PRIMARY KEY,
    oj TEXT NOT NULL,
    contest_id TEXT,
    title TEXT NOT NULL,
    start_epoch INTEGER,
    duration_sec INTEGER,
    rated_range TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS problems (
    problem_uid TEXT PRIMARY KEY,
    oj TEXT NOT NULL,
    contest_uid TEXT,
    contest_id TEXT,
    task_index TEXT,
    title TEXT NOT NULL,
    point REAL,
    url TEXT NOT NULL,
    difficulty INTEGER,
    solved_count INTEGER,
    tags_json TEXT,
    updated_epoch INTEGER,
    FOREIGN KEY (contest_uid) REFERENCES contests(contest_uid)
);

CREATE TABLE IF NOT EXISTS problem_tags (
    problem_uid TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (problem_uid, tag),
    FOREIGN KEY (problem_uid) REFERENCES problems(problem_uid)
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_uid TEXT PRIMARY KEY,
    oj TEXT NOT NULL,
    problem_uid TEXT NOT NULL,
    user_id TEXT NOT NULL,
    epoch_second INTEGER NOT NULL,
    result TEXT NOT NULL,
    language TEXT NOT NULL,
    exec_ms INTEGER,
    memory_kib INTEGER,
    url TEXT NOT NULL,
    FOREIGN KEY (problem_uid) REFERENCES problems(problem_uid)
);

CREATE TABLE IF NOT EXISTS sync_state (
    user_id TEXT NOT NULL,
    oj TEXT NOT NULL,
    key TEXT NOT NULL,
    last_submission_id TEXT,
    last_epoch INTEGER,
    PRIMARY KEY (user_id, oj, key)
);

CREATE INDEX IF NOT EXISTS idx_contests_oj_id ON contests(oj, contest_id);
CREATE INDEX IF NOT EXISTS idx_problems_contest_uid ON problems(contest_uid);
CREATE INDEX IF NOT EXISTS idx_problems_oj_contest ON problems(oj, contest_id);
CREATE INDEX IF NOT EXISTS idx_submissions_problem_uid ON submissions(problem_uid);
CREATE INDEX IF NOT EXISTS idx_submissions_user_epoch ON submissions(user_id, epoch_second);
CREATE INDEX IF NOT EXISTS idx_problem_tags_tag ON problem_tags(tag);

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
