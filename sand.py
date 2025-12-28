from config.loader import load_config
from db.schema import connect
from db.queries import list_contest_ids, list_contests_missing_submissions

config = load_config()
conn = connect()
contests = list_contest_ids(conn)
missing = list_contests_missing_submissions(conn, config.user_id, contests)
print("contests", len(contests))
print("missing", len(missing))
conn.close()
