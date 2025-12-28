PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS contests (
    contest_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_epoch INTEGER,
    duration_sec INTEGER,
    rated_range TEXT,
    category TEXT
);

CREATE TABLE IF NOT EXISTS problems (
    problem_id TEXT PRIMARY KEY,
    contest_id TEXT NOT NULL,
    task_index TEXT NOT NULL,
    title TEXT NOT NULL,
    point REAL,
    url TEXT NOT NULL,
    difficulty INTEGER,
    updated_epoch INTEGER,
    FOREIGN KEY (contest_id) REFERENCES contests(contest_id)
);

CREATE TABLE IF NOT EXISTS submissions (
    submission_id INTEGER PRIMARY KEY,
    problem_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    epoch_second INTEGER NOT NULL,
    result TEXT NOT NULL,
    language TEXT NOT NULL,
    exec_ms INTEGER,
    memory_kib INTEGER,
    url TEXT NOT NULL,
    FOREIGN KEY (problem_id) REFERENCES problems(problem_id)
);

CREATE INDEX IF NOT EXISTS idx_problems_contest_id ON problems(contest_id);
CREATE INDEX IF NOT EXISTS idx_submissions_problem_id ON submissions(problem_id);
CREATE INDEX IF NOT EXISTS idx_submissions_user_epoch ON submissions(user_id, epoch_second);
