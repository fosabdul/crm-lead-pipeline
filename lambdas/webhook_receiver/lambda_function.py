import json
import boto3
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = "crm-lead-pipeline"
S3_SOURCE_PREFIX = "source"
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/530917763100/crm-lead-delay-queue"
DELAY_SECONDS = int(os.environ.get("DELAY_SECONDS", 600))

s3 = boto3.client("s3")
sqs = boto3.client("sqs", region_name="us-east-1")

REQUIRED_FIELDS = ["lead_id", "date_created", "object_type", "action"]


def validate_event(webhook_event):
    missing = [f for f in REQUIRED_FIELDS if not webhook_event.get(f)]
    if missing:
        return False, f"Missing required fields: {missing}"
    if webhook_event.get("action") != "created":
        return False, f"Skipping non-created action: {webhook_event.get('action')}"
    if webhook_event.get("object_type") != "lead":
        return False, f"Skipping non-lead object: {webhook_event.get('object_type')}"
    return True, "OK"


def is_duplicate(lead_id):
    s3_key = f"{S3_SOURCE_PREFIX}/crm_event_{lead_id}.json"
    try:
        s3.head_object(Bucket=S3_BUCKET, Key=s3_key)
        return True
    except s3.exceptions.ClientError:
        return False


def lambda_handler(event, context):
    try:
        if "body" in event:
            body = event.get("body", "{}")
            if isinstance(body, str):
                body = json.loads(body)
        else:
            body = event

        webhook_event = body.get("event", {})
        lead_id = webhook_event.get("lead_id")

        if not lead_id:
            logger.error("No lead_id found in webhook event")
            return {"statusCode": 400, "body": json.dumps({"error": "Missing lead_id"})}

        # Validate required fields
        is_valid, message = validate_event(webhook_event)
        if not is_valid:
            logger.warning(f"Validation failed for {lead_id}: {message}")
            return {"statusCode": 400, "body": json.dumps({"error": message})}

        # Check for duplicate
        if is_duplicate(lead_id):
            logger.warning(f"Duplicate lead detected, skipping: {lead_id}")
            return {"statusCode": 200, "body": json.dumps({"message": "Duplicate lead skipped", "lead_id": lead_id})}

        logger.info(f"Processing new lead: {lead_id}")

        data = webhook_event.get("data", {})
        event_payload = {
            "subscription_id": body.get("subscription_id"),
            "event": {
                "id": webhook_event.get("id"),
                "date_created": webhook_event.get("date_created"),
                "date_updated": webhook_event.get("date_updated"),
                "organization_id": webhook_event.get("organization_id"),
                "object_type": webhook_event.get("object_type"),
                "object_id": webhook_event.get("object_id"),
                "lead_id": lead_id,
                "action": webhook_event.get("action"),
                "data": data
            }
        }

        s3_key = f"{S3_SOURCE_PREFIX}/crm_event_{lead_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=s3_key,
            Body=json.dumps(event_payload, indent=2),
            ContentType="application/json"
        )
        logger.info(f"Saved to S3: {s3_key}")

        sqs.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps({
                "lead_id": lead_id,
                "s3_key": s3_key
            }),
            DelaySeconds=DELAY_SECONDS
        )
        logger.info(f"Sent to SQS with {DELAY_SECONDS}s delay: {lead_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Lead received", "lead_id": lead_id})
        }

    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
