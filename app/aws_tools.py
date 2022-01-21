from datetime import datetime
import io
import json
import base64
from json.decoder import JSONDecodeError

import boto3

from tools import *


s3 = boto3.client("s3")
event_bridge = boto3.client("events")
secrets_manager = boto3.client("secretsmanager")


def in_aws():
    return os.environ.get("AWS_EXECUTION_ENV") is not None


def get_text_from_s3(bucket, key) -> str:
    print(f"Downloading text from S3://{bucket}/{key}")
    bytes_buffer = io.BytesIO()
    start = datetime.utcnow()
    s3.download_fileobj(Bucket=bucket, Key=key, Fileobj=bytes_buffer)
    seconds = round((datetime.utcnow() - start).total_seconds(), 3)
    print(f"Downloaded text in {seconds} seconds from S3://{bucket}/{key}")
    return bytes_buffer.getvalue().decode()


def save_text_to_s3(text, bucket, key):
    print(f"Saving to S3://{bucket}/{key}")
    start = datetime.utcnow()
    s3.put_object(Body=text, Bucket=bucket, Key=key)
    seconds = round((datetime.utcnow() - start).total_seconds(), 3)
    print(f"Saved in {seconds} seconds to S3://{bucket}/{key}")


def get_list_from_s3(bucket, key) -> list:
    raw_text = get_text_from_s3(bucket, key)
    return None if raw_text is None else raw_text.splitlines()


def save_list_to_s3(input_list, bucket, key):
    save_text_to_s3("\n".join(input_list), bucket, key)


def get_json_from_s3(bucket, key) -> dict:
    json_string = get_text_from_s3(bucket, key)
    return None if json_string is None else json.loads(json_string)


def save_json_to_s3(data, bucket, key, indent=2, compact=False, encoding="utf-8"):
    if compact:
        seperators = (",", ":")
        indent = None
    else:
        seperators = (", ", ": ")
    json_string = json.dumps(
        data, 
        indent=indent, 
        ensure_ascii=False, 
        separators=seperators)
    save_text_to_s3(json_string, bucket, key)


def get_secret(secret_id):
    print(f"Retreiving '{secret_id}' from secrets manager.")
    get_secret_value_response = secrets_manager.get_secret_value(SecretId=secret_id)

    if "SecretString" in get_secret_value_response:
        secret = get_secret_value_response["SecretString"]
    else:
        secret = base64.b64decode(get_secret_value_response["SecretBinary"])

    try:
        return json.loads(secret)
    except JSONDecodeError:
        print(f"Could not decode secret string into JSON, returning pure string instead.")
        return secret


def update_event_cron_rule(event_name, cron_string):
    cron = "cron(0/{} {}-{} ? * * *)".format(minute_interval, HOUR_START_TWEETS, HOUR_END_TWEETS)
    eventBridge.put_rule(Name=event_name, ScheduleExpression=cron)