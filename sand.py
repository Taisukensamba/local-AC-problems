from config.loader import load_config
from db.schema import connect
from db.queries import list_contest_uids, list_contests_missing_submissions
from oj.atcoder import atcoder_oj

config = load_config()
conn = connect()
contests = list_contest_uids(conn, atcoder_oj.name)
missing = list_contests_missing_submissions(conn, config.atcoder.user_id, contests)
print("contests", len(contests))
print("missing", len(missing))
conn.close()
