import os

from aws_tools import get_json_from_s3

S3_BUCKET = os.environ["MPE_S3_BUCKET"]
S3_EXPENSE_QUEUE_KEY = "new_expenses_queue.json"
S3_PREV_CLAIM_NUMBERS_KEY = "previous_claimNumbers.txt"
MEMBERS_OF_NOTE_IDS = set(get_json_from_s3(S3_BUCKET, "members_of_note.json").values())
GROUP_THRESHOLDS = get_json_from_s3(S3_BUCKET, "group_thresholds.json")
