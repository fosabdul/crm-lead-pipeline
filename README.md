Real-Time CRM Lead Processing and Notification System

Overview

This system automatically captures new leads from Close CRM, waits 10 minutes
for a sales rep to be assigned, enriches the lead with owner details, and sends
an email notification to the sales team.

---

Architecture

Close CRM sends a webhook event to API Gateway, which triggers Lambda 1.
Lambda 1 saves the raw lead data to S3 and places the lead ID in an SQS queue
with a 10-minute delay. After the delay, Lambda 2 fetches the lead owner from
a public S3 bucket, merges the data, saves the enriched result, and sends an
email via AWS SES.

---

AWS Services

API Gateway   Receives webhook events from Close CRM
Lambda 1      Parses event, saves to S3, sends to SQS
S3            Stores raw events in source/ and enriched data in target/
SQS           Holds the lead for 10 minutes before processing
Lambda 2      Looks up owner, merges data, sends email
SES           Delivers email notification to the sales team

---

Project Structure

crm-lead-pipeline/
  lambdas/
    webhook_receiver/
      lambda_function.py
    lead_processor/
      lambda_function.py
  docs/
  README.md
  .gitignore

---

Setup

1. Create S3 bucket crm-lead-pipeline with folders: source/ and target/
2. Create SQS queue crm-lead-delay-queue with 600-second delivery delay
3. Create Lambda 1 crm-webhook-receiver using Python 3.12, triggered by API Gateway POST /crm
4. Create Lambda 2 crm-lead-processor using Python 3.12, triggered by SQS
5. Verify sender email in AWS SES before sending notifications

API Gateway endpoint:
https://s6rv4u911g.execute-api.us-east-1.amazonaws.com/deploy/crm

---

Notification Format

Name          Fetched from CRM webhook data
Lead ID       Fetched from CRM webhook data
Created Date  Fetched from CRM webhook data
Label         Fetched from CRM webhook data
Email         Fetched from lead owner lookup
Lead Owner    Fetched from lead owner lookup
Funnel        Fetched from lead owner lookup

---

Testing

Send a test webhook with this command:

curl -X POST https://s6rv4u911g.execute-api.us-east-1.amazonaws.com/deploy/crm \
  -H "Content-Type: application/json" \
  -d '{
    "subscription_id": "whsub_test",
    "event": {
      "id": "ev_test",
      "date_created": "2025-05-20T12:14:56.446000",
      "date_updated": "2025-05-20T12:14:56.446000",
      "organization_id": "orga_test",
      "object_type": "lead",
      "object_id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA",
      "lead_id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA",
      "action": "created",
      "data": {
        "display_name": "Lowell Bast",
        "date_created": "2025-05-20T12:14:56.409000+00:00",
        "status_label": "Potential",
        "id": "lead_niuYPXlw6vnFQIhwZCKDaaKv9XMQs9KA5NgxhNRBgaA"
      }
    }
  }'

After 10 minutes check S3 target/ for the enriched file and Gmail for the alert.

---

Error Handling

Both Lambda functions log to CloudWatch. Missing fields return a 400 response.
Failed lookups are logged and processing continues with available data.
SQS retries failed messages automatically.

---

Contact

For Close CRM webhook registration contact Azmat or Ninad with the API Gateway
endpoint URL listed above.
