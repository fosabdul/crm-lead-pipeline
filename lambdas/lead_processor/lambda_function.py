import json
import boto3
import urllib.request
import urllib.error
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = "crm-lead-pipeline"
S3_SOURCE_PREFIX = "source"
S3_TARGET_PREFIX = "target"
LEAD_OWNER_BUCKET = "dea-lead-owner"
SENDER_EMAIL = "fosabdul@gmail.com"
RECIPIENT_EMAIL = "fosabdul@gmail.com"

s3 = boto3.client("s3")
ses = boto3.client("ses", region_name="us-east-1")


def get_lead_owner(lead_id):
    url = f"https://{LEAD_OWNER_BUCKET}.s3.us-east-1.amazonaws.com/{lead_id}.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        logger.warning(f"Lead owner not found for {lead_id}: {e.code}")
        return None
    except Exception as e:
        logger.error(f"Error fetching lead owner: {str(e)}")
        return None


def get_crm_event(s3_key):
    try:
        response = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        return json.loads(response["Body"].read().decode())
    except Exception as e:
        logger.error(f"Error fetching CRM event from S3: {str(e)}")
        return None


def save_enriched_data(lead_id, enriched_data):
    s3_key = f"{S3_TARGET_PREFIX}/crm_event_{lead_id}.json"
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=s3_key,
        Body=json.dumps(enriched_data, indent=2),
        ContentType="application/json"
    )
    logger.info(f"Saved enriched data to S3: {s3_key}")


def send_email_notification(crm_event, owner_data):
    event_data = crm_event.get("event", {})
    lead_data = event_data.get("data", {})

    display_name = lead_data.get("display_name", "N/A")
    lead_id = event_data.get("lead_id", "N/A")
    date_created = lead_data.get("date_created", "N/A")
    status_label = lead_data.get("status_label", "N/A")

    lead_email = owner_data.get("lead_email", "N/A") if owner_data else "N/A"
    lead_owner = owner_data.get("lead_owner", "N/A") if owner_data else "N/A"
    funnel = owner_data.get("funnel", "N/A") if owner_data else "N/A"

    subject = f"New Lead Alert — {display_name}"

    body_text = f"""
New Lead Alert

Name:         {display_name}
Lead ID:      {lead_id}
Created Date: {date_created}
Label:        {status_label}
Email:        {lead_email}
Lead Owner:   {lead_owner}
Funnel:       {funnel}
"""

    body_html = f"""
<html>
<body style="font-family: Arial, sans-serif; padding: 20px;">
  <h2 style="color: #232F3E;">New Lead Alert</h2>
  <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
    <tr style="background-color: #f2f2f2;">
      <td style="padding: 10px; font-weight: bold; width: 150px;">Name</td>
      <td style="padding: 10px;">{display_name}</td>
    </tr>
    <tr>
      <td style="padding: 10px; font-weight: bold;">Lead ID</td>
      <td style="padding: 10px;">{lead_id}</td>
    </tr>
    <tr style="background-color: #f2f2f2;">
      <td style="padding: 10px; font-weight: bold;">Created Date</td>
      <td style="padding: 10px;">{date_created}</td>
    </tr>
    <tr>
      <td style="padding: 10px; font-weight: bold;">Label</td>
      <td style="padding: 10px;">{status_label}</td>
    </tr>
    <tr style="background-color: #f2f2f2;">
      <td style="padding: 10px; font-weight: bold;">Email</td>
      <td style="padding: 10px;">{lead_email}</td>
    </tr>
    <tr>
      <td style="padding: 10px; font-weight: bold;">Lead Owner</td>
      <td style="padding: 10px;">{lead_owner}</td>
    </tr>
    <tr style="background-color: #f2f2f2;">
      <td style="padding: 10px; font-weight: bold;">Funnel</td>
      <td style="padding: 10px;">{funnel}</td>
    </tr>
  </table>
</body>
</html>
"""

    ses.send_email(
        Source=SENDER_EMAIL,
        Destination={"ToAddresses": [RECIPIENT_EMAIL]},
        Message={
            "Subject": {"Data": subject},
            "Body": {
                "Text": {"Data": body_text},
                "Html": {"Data": body_html}
            }
        }
    )
    logger.info(f"Email sent for lead: {lead_id}")


def lambda_handler(event, context):
    for record in event.get("Records", []):
        try:
            message = json.loads(record["body"])
            lead_id = message.get("lead_id")
            s3_key = message.get("s3_key")

            if not lead_id or not s3_key:
                logger.error("Missing lead_id or s3_key in SQS message")
                continue

            logger.info(f"Processing lead: {lead_id}")

            crm_event = get_crm_event(s3_key)
            if not crm_event:
                logger.error(f"Could not fetch CRM event for {lead_id}")
                continue

            owner_data = get_lead_owner(lead_id)
            if not owner_data:
                logger.warning(f"No owner data found for {lead_id}, continuing anyway")

            enriched = {**crm_event}
            if owner_data:
                enriched["owner_data"] = owner_data
            save_enriched_data(lead_id, enriched)

            send_email_notification(crm_event, owner_data)

            logger.info(f"Successfully processed lead: {lead_id}")

        except Exception as e:
            logger.error(f"Error processing record: {str(e)}")
            raise

    return {"statusCode": 200, "body": "OK"}
