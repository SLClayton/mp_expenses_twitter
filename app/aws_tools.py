import io
import json

import boto3
from botocore.errorfactory import ClientError


s3 = boto3.client("s3")
event_bridge = boto3.client('events')


def get_text_from_s3(bucket, key) -> str:
    bytes_buffer = io.BytesIO()
    s3.download_fileobj(Bucket=bucket, Key=key, Fileobj=bytes_buffer)
    return bytes_buffer.getvalue().decode()


def get_list_from_s3(bucket, key) -> list:
    raw_text = get_text_from_s3(bucket, key)
    return None if raw_text is None else raw_text.splitlines()


def save_list_to_s3(input_list, bucket, key):
    s3.put_object(Body="\n".join(input_list),  Bucket=bucket, Key=key)


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
    s3.put_object(Body=json_string,  Bucket=bucket, Key=key)