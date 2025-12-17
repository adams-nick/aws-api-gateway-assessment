#!/bin/bash

echo "Deploying Lambda functions..."

# Zip and upload Lambda 1
cd lambdas/lambda1
zip -r lambda1.zip index.mjs
aws s3 cp lambda1.zip s3://scansource-lambda-bucket/
aws lambda update-function-code \
  --function-name NodeFunction \
  --s3-bucket scansource-lambda-bucket \
  --s3-key lambda1.zip \
  --region us-west-2
cd ../..

# Zip and upload Lambda 2
cd lambdas/lambda2
zip -r lambda2.zip lambda_function.py
aws s3 cp lambda2.zip s3://scansource-lambda-bucket/
aws lambda update-function-code \
  --function-name PythonFunction \
  --s3-bucket scansource-lambda-bucket \
  --s3-key lambda2.zip \
  --region us-west-2
cd ../..

echo "Lambda functions deployed successfully."