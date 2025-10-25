#!/bin/bash
# Set up API Gateway HTTP API for tracking endpoints

set -e

API_NAME="collagen-tracking-api"
LAMBDA_FUNCTION="collagen-tracking-router"
REGION="us-east-1"

echo "=== Setting up API Gateway HTTP API ==="
echo ""

# Get Lambda ARN
LAMBDA_ARN=$(aws lambda get-function --function-name "${LAMBDA_FUNCTION}" --region "${REGION}" --query 'Configuration.FunctionArn' --output text)
echo "Lambda ARN: ${LAMBDA_ARN}"

# 1. Create HTTP API
echo "1. Creating HTTP API"
API_ID=$(aws apigatewayv2 create-api \
    --name "${API_NAME}" \
    --protocol-type HTTP \
    --region "${REGION}" \
    --query 'ApiId' \
    --output text 2>/dev/null || true)

if [ -z "$API_ID" ]; then
    # API might already exist, try to find it
    API_ID=$(aws apigatewayv2 get-apis --region "${REGION}" --query "Items[?Name=='${API_NAME}'].ApiId" --output text)
    if [ -z "$API_ID" ]; then
        echo "ERROR: Failed to create API"
        exit 1
    fi
    echo "   API already exists: ${API_ID}"
else
    echo "   ✓ Created API: ${API_ID}"
fi

# 2. Create Lambda integration
echo "2. Creating Lambda integration"
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "${API_ID}" \
    --integration-type AWS_PROXY \
    --integration-uri "${LAMBDA_ARN}" \
    --payload-format-version 2.0 \
    --region "${REGION}" \
    --query 'IntegrationId' \
    --output text)

echo "   ✓ Created integration: ${INTEGRATION_ID}"

# 3. Create route: ANY /t/{proxy+}
echo "3. Creating route: ANY /t/{proxy+}"
ROUTE_ID=$(aws apigatewayv2 create-route \
    --api-id "${API_ID}" \
    --route-key 'ANY /t/{proxy+}' \
    --target "integrations/${INTEGRATION_ID}" \
    --region "${REGION}" \
    --query 'RouteId' \
    --output text)

echo "   ✓ Created route: ${ROUTE_ID}"

# 4. Create $default stage (auto-deploy)
echo "4. Creating $default stage"
STAGE_NAME='$default'
aws apigatewayv2 create-stage \
    --api-id "${API_ID}" \
    --stage-name "${STAGE_NAME}" \
    --auto-deploy \
    --region "${REGION}" >/dev/null 2>&1 || echo "   Stage already exists"

echo "   ✓ Stage ready"

# 5. Grant API Gateway permission to invoke Lambda
echo "5. Granting API Gateway invoke permission"
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
SOURCE_ARN="arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*/t/*"

aws lambda add-permission \
    --function-name "${LAMBDA_FUNCTION}" \
    --statement-id "apigateway-invoke-$(date +%s)" \
    --action lambda:InvokeFunction \
    --principal apigateway.amazonaws.com \
    --source-arn "${SOURCE_ARN}" \
    --region "${REGION}" >/dev/null 2>&1 || echo "   Permission already exists"

echo "   ✓ Permission granted"

# Get API endpoint
API_ENDPOINT=$(aws apigatewayv2 get-api --api-id "${API_ID}" --region "${REGION}" --query 'ApiEndpoint' --output text)

echo ""
echo "=== API Gateway Setup Complete ==="
echo ""
echo "API ID: ${API_ID}"
echo "API Endpoint: ${API_ENDPOINT}"
echo ""
echo "Test URLs:"
echo "  ${API_ENDPOINT}/t/test_prototype/abc12345/20251025T000000Z,10=5x2.jpg"
echo "  ${API_ENDPOINT}/t/test_prototype/abc12345/validate"
echo "  ${API_ENDPOINT}/t/test_prototype/abc12345/subscribe"
echo ""
echo "Next: Set up custom domain (collagen.pauseai.info)"
