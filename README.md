# AWS API Gateway with Cognito Authentication

A production-ready AWS serverless application demonstrating API Gateway with Cognito authentication, Lambda functions calling external APIs, and complete infrastructure as code using CloudFormation.

## Overview

This project implements a secure REST API with two endpoints:

- **Stocks API**: Calculates investment returns using real-time stock prices from Alpha Vantage
- **Weather API**: Provides outerwear recommendations based on current weather from Open-Meteo

**Technologies**: API Gateway, AWS Cognito, Lambda (Node.js 24.x & Python 3.12), CloudFormation, Secrets Manager, CloudWatch Logs + Alarms, IAM Roles

---

## Architecture

### Components

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         API Gateway (REST API)          │
│  ┌─────────────────────────────────┐   │
│  │   Cognito Authorizer            │   │
│  └─────────────────────────────────┘   │
│  ┌─────────────┐  ┌─────────────────┐  │
│  │ GET /stocks │  │ GET /weather    │  │
│  │ (cached)    │  │ (cached)        │  │
│  └──────┬──────┘  └────────┬────────┘  │
└─────────┼──────────────────┼───────────┘
          │                  │
          ▼                  ▼
   ┌────────────┐     ┌────────────┐
   │  Lambda 1  │     │  Lambda 2  │
   │ (Node.js)  │     │  (Python)  │
   └──────┬─────┘     └──────┬─────┘
          │                  │
          ▼                  ▼
   ┌─────────────┐    ┌─────────────┐
   │ Alpha       │    │ Open-Meteo  │
   │ Vantage API │    │ Weather API │
   └─────────────┘    └─────────────┘
```

### AWS Resources Created

- **API Gateway**: REST API with 2 endpoints, 300-second caching, encryption
- **Cognito User Pool**: Authentication with email-based login
- **Lambda Functions**:
  - Node.js 24.x (Stock calculator with Secrets Manager integration)
  - Python 3.12 (Weather recommendations with geocoding)
- **IAM Roles**: Lambda execution, API Gateway CloudWatch logging
- **Secrets Manager**: Secure Alpha Vantage API key storage
- **CloudWatch**: Alarms for Lambda errors and API 5XX errors

---

## External Services

### Lambda 1: Alpha Vantage Stock API (Node.js)

**Purpose**: Calculate investment returns by comparing initial purchase price with current stock price.

**Why chosen**:

- Real-world financial data use case
- Demonstrates secure API key management via Secrets Manager
- Shows proper error handling for rate limits and invalid symbols

**Endpoint**: `GET /api/v1/stocks?symbol=AAPL&initialPrice=150.00`

**Features**:

- Real-time stock quotes via Alpha Vantage GLOBAL_QUOTE API
- Retry logic with exponential backoff
- Rate limit detection (429 handling)
- Symbol validation (1-5 uppercase letters)

### Lambda 2: Open-Meteo Weather API (Python)

**Purpose**: Recommend appropriate outerwear based on current weather conditions.

**Why chosen**:

- Free public API (no API key required)
- Demonstrates REST API Status code responses
- **Endpoint**: `GET /api/v1/weather?city=Toronto`

  **Features**:

- City name to GPS coordinates conversion
- Temperature-based recommendations (winter coat, light jacket, hoodie)
- Precipitation probability for rain jacket suggestions
- Type hints and comprehensive docstrings

---

## Prerequisites

- **AWS CLI** installed and configured (`aws configure`)
- **AWS Account** with permissions to create CloudFormation stacks, Lambda, API Gateway, Cognito
- **Bash shell** (macOS/Linux or WSL on Windows)
- **jq** (optional, for JSON formatting): `brew install jq` or `apt-get install jq`

---

## Deployment Guide

### Step 1: Prepare Lambda Functions

First, create an S3 bucket and upload the Lambda function code:

```bash
# Create S3 bucket for Lambda deployment packages
aws s3 mb s3://scansource-lambda-bucket --region us-west-2

# Package and upload Lambda 1 (Node.js)
cd lambdas/lambda1
npm install
zip -r lambda1.zip index.mjs node_modules/
aws s3 cp lambda1.zip s3://scansource-lambda-bucket/lambda1.zip
cd ../..

# Package and upload Lambda 2 (Python)
cd lambdas/lambda2
zip lambda2.zip lambda_function.py
aws s3 cp lambda2.zip s3://scansource-lambda-bucket/lambda2.zip
cd ../..
```

### Step 2: Deploy CloudFormation Stack

Deploy the complete infrastructure using CloudFormation:

```bash
aws cloudformation create-stack \
  --stack-name scansource-api-assessment-stack \
  --template-body file://cloudformation/main.yaml \
  --capabilities CAPABILITY_IAM \
  --parameters \
    ParameterKey=LambdaFunctionsS3Bucket,ParameterValue=scansource-lambda-bucket \
    ParameterKey=AlphaVantageApiKey,ParameterValue=M7LYER0TKQDPM762 \
  --region us-west-2

# Wait for stack creation to complete
aws cloudformation wait stack-create-complete \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2
```

**Note**: The Alpha Vantage API key `M7LYER0TKQDPM762` is provided for assessment purposes.

### Step 3: Retrieve Stack Outputs

Get the deployed resource information:

```bash
aws cloudformation describe-stacks \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs' \
  --output table
```

**Key Outputs**:

- `ApiEndpointUrl`: Base API URL
- `StocksEndpoint`: Full stocks endpoint URL
- `WeatherEndpoint`: Full weather endpoint URL
- `UserPoolId`: Cognito User Pool ID
- `UserPoolClientId`: Client ID for authentication

### Step 4: Create Cognito User

Create a test user for API authentication:

```bash
# Get User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Create user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --user-attributes Name=email,Value=testuser@example.com Name=email_verified,Value=true \
  --temporary-password TempPassword123! \
  --message-action SUPPRESS \
  --region us-west-2

# Set permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --password MyPassword123! \
  --permanent \
  --region us-west-2
```

**Credentials**:

- Email: `testuser@example.com`
- Password: `MyPassword123!`

---

## Testing Instructions

### Authenticate with Cognito

Get an authentication token (valid for 1 hour):

```bash
# Get Client ID
CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolClientId`].OutputValue' \
  --output text)

# Authenticate and get token
TOKEN=$(aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id $CLIENT_ID \
  --auth-parameters USERNAME=testuser@example.com,PASSWORD=MyPassword123! \
  --region us-west-2 \
  --query 'AuthenticationResult.IdToken' \
  --output text)

echo "Token: $TOKEN"
```

### Test Stocks Endpoint

#### Valid Stock Request

```bash
API_URL=$(aws cloudformation describe-stacks \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`StocksEndpoint`].OutputValue' \
  --output text)

curl -H "Authorization: Bearer $TOKEN" \
  "$API_URL?symbol=AAPL&initialPrice=150.00"
```

**Expected Response (200)**:

```json
{
  "success": true,
  "data": {
    "symbol": "AAPL",
    "initialPrice": 150,
    "currentPrice": 272.19,
    "percentageReturn": 81.46,
    "isProfit": true
  }
}
```

#### Invalid Symbol

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$API_URL?symbol=INVALID123&initialPrice=100"
```

**Expected Response (400)**:

```json
{
  "success": false,
  "error": "Invalid symbol format. Must be 1-5 letters."
}
```

#### Missing Parameters

```bash
curl -H "Authorization: Bearer $TOKEN" "$API_URL"
```

**Expected Response (400)**:

```json
{
  "success": false,
  "error": "Missing required parameters: symbol, initialPrice"
}
```

#### Unauthorized Request (No Token)

```bash
curl "$API_URL?symbol=AAPL&initialPrice=150.00"
```

**Expected Response (401)**:

```json
{
  "message": "Unauthorized"
}
```

### Test Weather Endpoint

#### Valid Weather Request

```bash
WEATHER_URL=$(aws cloudformation describe-stacks \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`WeatherEndpoint`].OutputValue' \
  --output text)

curl -H "Authorization: Bearer $TOKEN" \
  "$WEATHER_URL?city=Toronto"
```

**Expected Response (200)**:

```json
{
  "success": true,
  "data": {
    "location": "Toronto, Canada",
    "temperature": -1.5,
    "precipitationProbability": 2,
    "outerwearRecommended": ["winter coat"]
  }
}
```

#### Invalid City

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "$WEATHER_URL?city=ZZZInvalidCity999"
```

**Expected Response (404)**:

```json
{
  "success": false,
  "error": "City not found: ZZZInvalidCity999"
}
```

#### Missing Parameters

```bash
curl -H "Authorization: Bearer $TOKEN" "$WEATHER_URL"
```

**Expected Response (400)**:

```json
{
  "success": false,
  "error": "Missing required parameter: city"
}
```

---

## CloudFormation Resources

The `cloudformation/main.yaml` template creates the following resources:

### Core Services

- **AWS::ApiGateway::RestApi**: REST API with regional endpoint
- **AWS::ApiGateway::Stage**: Production stage with caching enabled
- **AWS::Cognito::UserPool**: User pool with email authentication
- **AWS::Cognito::UserPoolClient**: App client for authentication
- **AWS::Lambda::Function** (x2): Node.js 24.x and Python 3.12 functions

### Security & Permissions

- **AWS::IAM::Role** (x2): Lambda execution role, API Gateway CloudWatch role
- **AWS::Lambda::Permission** (x2): API Gateway invoke permissions
- **AWS::ApiGateway::Authorizer**: Cognito user pool authorizer
- **AWS::SecretsManager::Secret**: Alpha Vantage API key storage

### Monitoring

- **AWS::CloudWatch::Alarm** (x3): Lambda1 errors, Lambda2 errors, API 5XX errors
- **AWS::ApiGateway::Account**: CloudWatch logging configuration

### Configuration

- **Parameters**: LambdaFunctionsS3Bucket, AlphaVantageApiKey
- **Outputs**: 13 outputs including endpoints, IDs, ARNs, log groups

---

## Assumptions & Limitations

### Assumptions

1. **AWS Region**: Deployment assumes `us-west-2` region
2. **S3 Bucket Availability**: Bucket name `scansource-lambda-bucket` must be available in your account
3. **API Key Validity**: Alpha Vantage API key `M7LYER0TKQDPM762` is valid and provided for assessment.
4. **AWS Permissions**: User has permissions to create all required resources (CloudFormation, Lambda, API Gateway, Cognito, IAM, Secrets Manager, CloudWatch, S3)
5. **Node.js Dependencies**: Lambda 1 uses `@aws-sdk/client-secrets-manager` (bundled in deployment package)

### Limitations

1. **Cache Provisioning Time**: API Gateway cache cluster takes 5-10 minutes to provision during initial stack creation
2. **Cache TTL**: Responses cached for 300 seconds (5 minutes) - stock prices may be stale
3. **No Custom Domain**: API uses default API Gateway domain (can be extended with Route53 + ACM)
4. **Single Region**: Infrastructure deployed to single region (no multi-region redundancy)
5. **Hardcoded API Key**: I have implemented AWS Secrets Manager, but have simply provided the hardcoded API key command within this document. In real-world environment this would be stored securely externally.

### Production Enhancements Not Included

- Custom domain name with SSL certificate
- WAF rules for API protection
- X-Ray tracing for distributed debugging
- Multi-region failover
- CI/CD pipeline for automated deployments + staging

---

## Additional Features

This implementation includes production-ready features:

- **Structured Logging**: JSON-formatted logs for CloudWatch Insights queries
- **Retry Logic**: Exponential backoff for transient failures (stocks API)
- **Input Validation**: Parameter validation with clear error messages
- **Error Handling**: Comprehensive error handling with appropriate HTTP status codes
- **Secrets Management**: API keys stored in Secrets Manager (not hardcoded)
- **Resource Tagging**: All resources tagged for cost tracking and management
- **CloudWatch Alarms**: Automated alerting for Lambda errors and API failures
- **API Caching**: Reduces costs and latency with encrypted cache storage
- **Type Safety**: JSDoc (Node.js) and type hints (Python) for better code quality
- **Rate Limit Handling**: Fail-fast on 429 errors to avoid compounding issues

---

## Cleanup

To remove all resources and avoid ongoing charges:

```bash
# Delete CloudFormation stack
aws cloudformation delete-stack \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2

# Wait for deletion to complete
aws cloudformation wait stack-delete-complete \
  --stack-name scansource-api-assessment-stack \
  --region us-west-2

# Empty and delete S3 bucket
aws s3 rm s3://scansource-lambda-bucket --recursive
aws s3 rb s3://scansource-lambda-bucket
```

**Note**: Cognito User Pool has `DeletionPolicy: Retain` to protect user data. To fully delete it:

```bash
# Get User Pool ID
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 60 --region us-west-2 \
  --query "UserPools[?Name=='scansource-api-assessment-stack-UserPool'].Id" --output text)

# Delete User Pool (if found)
if [ -n "$USER_POOL_ID" ]; then
  aws cognito-idp delete-user-pool --user-pool-id $USER_POOL_ID --region us-west-2
fi
```
