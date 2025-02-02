from datetime import datetime
import io
import json
from typing import Dict, Any, Union, List

import boto3
from botocore.exceptions import ClientError

from tools import *

TABLE_NAME = os.getenv("MPE_DDB_TABLE_NAME")

s3 = boto3.client("s3")
secrets_manager = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")
ddb_table = dynamodb.Table(TABLE_NAME)


def in_aws() -> bool:
    return os.environ.get("AWS_EXECUTION_ENV") is not None


def get_text_from_s3(bucket, key) -> str:
    print(f"Downloading text from S3://{bucket}/{key}")
    bytes_buffer = io.BytesIO()
    start = datetime.utcnow()
    try:
        s3.download_fileobj(Bucket=bucket, Key=key, Fileobj=bytes_buffer)
    except ClientError as e:
        if e.response['Error']['Code'] == "404":
            return None
        raise
    seconds = round((datetime.utcnow() - start).total_seconds(), 3)
    print(f"Downloaded text in {seconds} seconds from S3://{bucket}/{key}")
    return bytes_buffer.getvalue().decode()


def save_text_to_s3(text, bucket, key) -> None:
    print(f"Saving to S3://{bucket}/{key}")
    start = datetime.utcnow()
    s3.put_object(Body=text, Bucket=bucket, Key=key)
    seconds = round((datetime.utcnow() - start).total_seconds(), 3)
    print(f"Saved in {seconds} seconds to S3://{bucket}/{key}")


def get_list_from_s3(bucket, key) -> List[str]:
    raw_text = get_text_from_s3(bucket, key)
    return None if raw_text is None else raw_text.splitlines()


def save_list_to_s3(input_list, bucket, key) -> None:
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


def get_secret_dict(name: str) -> Dict[str, Any]:
    return json.loads(get_secret_string(name))


def get_secret_string(name: str) -> str:
    print(f"Requesting secret from AWS secret manager: {name}")
    secret_str = secrets_manager.get_secret_value(SecretId=name)["SecretString"]
    print(f"Secret found.")
    return secret_str


def save_item_to_db(item: dict) -> None:
    ddb_table.put_item(Item=item)


def item_in_db(item_id: Union[str, int]) -> bool:
    try:
        response = ddb_table.get_item(Key={"expense_id": str(item_id)})
        return "Item" in response
    except Exception as e:
        print("Error checking item:", e)
