CREATE TABLE IF NOT EXISTS sync_state (
    user_id TEXT NOT NULL,
    contest_id TEXT NOT NULL,
    last_submission_id INTEGER,
    last_epoch INTEGER,
    PRIMARY KEY (user_id, contest_id)
);
