#!/bin/bash

# Define the endpoint for our mock AWS (Moto)
ENDPOINT="http://aws-mock:5000"
REGION="af-south-1"
ACCOUNT_ID="123456789012"

echo "Configuring Mock AWS Environment (Moto)..."

# 1. Create the Main Transaction SNS Topic
echo "Creating SNS Topic: transaction-events..."
aws --endpoint-url=$ENDPOINT sns create-topic --name transaction-events --region $REGION

TOPIC_ARN="arn:aws:sns:$REGION:$ACCOUNT_ID:transaction-events"

# 2. Create SQS Queues for each Consumer
QUEUES=("velocity-queue" "amount-queue" "blacklist-queue" "aggregator-queue")

for QUEUE in "${QUEUES[@]}"; do
    echo "Creating Queue: $QUEUE..."
    aws --endpoint-url=$ENDPOINT sqs create-queue --queue-name $QUEUE --region $REGION
    
    QUEUE_ARN="arn:aws:sqs:$REGION:$ACCOUNT_ID:$QUEUE"

    # 3. Add Policy to allow SNS to send messages to this SQS queue
    # This is often the "missing link" in SQS/SNS local setups
    POLICY='{
      "Version":"2012-10-17",
      "Statement":[
        {
          "Effect":"Allow",
          "Principal":"*",
          "Action":"sqs:SendMessage",
          "Resource":"'"$QUEUE_ARN"'",
          "Condition":{
            "ArnEquals":{
              "aws:SourceArn":"'"$TOPIC_ARN"'"
            }
          }
        }
      ]
    }'
    
    aws --endpoint-url=$ENDPOINT sqs set-queue-attributes \
        --queue-url "$ENDPOINT/123456789012/$QUEUE" \
        --attributes "{\"Policy\":$(echo $POLICY | jq -R .)}"

    # 4. Subscribe each Queue to the SNS Topic (Fan-Out)
    echo "Subscribing $QUEUE to SNS Topic..."
    aws --endpoint-url=$ENDPOINT sns subscribe \
        --topic-arn $TOPIC_ARN \
        --protocol sqs \
        --notification-endpoint $QUEUE_ARN \
        --region $REGION
done

echo "Mock AWS Environment setup complete!"