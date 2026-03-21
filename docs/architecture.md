Architecture Overview - Real-Time CRM Lead Processing System

Step 1  Close CRM
        Lead created fires a webhook event (action: created, object_type: lead)
        Sends HTTPS POST to API Gateway endpoint

Step 2  API Gateway - crm-webhook-api
        REST API deployed on stage: deploy
        Route: POST /crm with Lambda proxy integration

Step 3  Lambda 1 - crm-webhook-receiver (Python 3.12)
        Parses webhook body and extracts lead_id and display_name
        Saves raw event to S3 source/ as crm_event_{lead_id}.json
        Sends lead_id to SQS queue with 600-second delay
        IAM: S3 PutObject + SQS SendMessage

Step 4  SQS Queue - crm-lead-delay-queue
        Standard queue with 10-minute delivery delay
        Holds message until CRM assigns a lead owner
        Triggers Lambda 2 automatically after delay

Step 5  Lambda 2 - crm-lead-processor (Python 3.12)
        Reads original event from S3 source/
        Fetches lead owner from public S3 bucket dea-lead-owner
        URL: https://dea-lead-owner.s3.us-east-1.amazonaws.com/{lead_id}.json
        Merges CRM data + owner data
        Saves enriched JSON to S3 target/
        Sends email notification via AWS SES
        IAM: S3 GetObject/PutObject + SES SendEmail

Step 6  Gmail Notification
        Recipient: fosabdul@gmail.com
        Fields: Name, Lead ID, Created Date, Label, Email, Lead Owner, Funnel
