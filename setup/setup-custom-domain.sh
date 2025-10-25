#!/bin/bash
# Set up custom domain for API Gateway: collagen.pauseai.info

set -e

DOMAIN_NAME="collagen.pauseai.info"
API_ID="ulfu5jmrjh"  # From previous step
REGION="us-east-1"

echo "=== Setting up custom domain: ${DOMAIN_NAME} ==="
echo ""

# 1. Request ACM certificate (must be in us-east-1 for API Gateway)
echo "1. Requesting ACM certificate for ${DOMAIN_NAME}"
CERT_ARN=$(aws acm request-certificate \
    --domain-name "${DOMAIN_NAME}" \
    --validation-method DNS \
    --region "${REGION}" \
    --query 'CertificateArn' \
    --output text 2>/dev/null || true)

if [ -z "$CERT_ARN" ]; then
    # Certificate might already exist
    CERT_ARN=$(aws acm list-certificates --region "${REGION}" \
        --query "CertificateSummaryList[?DomainName=='${DOMAIN_NAME}'].CertificateArn" \
        --output text | head -1)

    if [ -z "$CERT_ARN" ]; then
        echo "ERROR: Failed to request certificate"
        exit 1
    fi
    echo "   Certificate already exists: ${CERT_ARN}"
else
    echo "   ✓ Certificate requested: ${CERT_ARN}"
fi

# 2. Get DNS validation records
echo "2. Getting DNS validation records"
echo ""
echo "   To validate the certificate, add these DNS records to pauseai.info:"
echo ""

aws acm describe-certificate \
    --certificate-arn "${CERT_ARN}" \
    --region "${REGION}" \
    --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
    --output table

echo ""
echo "   Record Type: CNAME"
echo ""
read -p "Press Enter after adding DNS records and waiting for validation..."

# 3. Wait for certificate validation
echo "3. Waiting for certificate validation..."
aws acm wait certificate-validated \
    --certificate-arn "${CERT_ARN}" \
    --region "${REGION}"

echo "   ✓ Certificate validated"

# 4. Create API Gateway custom domain
echo "4. Creating custom domain in API Gateway"
DOMAIN_CONFIG=$(aws apigatewayv2 create-domain-name \
    --domain-name "${DOMAIN_NAME}" \
    --domain-name-configurations CertificateArn="${CERT_ARN}" \
    --region "${REGION}" 2>/dev/null || true)

if [ -z "$DOMAIN_CONFIG" ]; then
    # Domain might already exist
    DOMAIN_CONFIG=$(aws apigatewayv2 get-domain-name \
        --domain-name "${DOMAIN_NAME}" \
        --region "${REGION}")
    echo "   Domain already exists"
else
    echo "   ✓ Domain created"
fi

# Get API Gateway domain name for DNS
API_GW_DOMAIN=$(echo "$DOMAIN_CONFIG" | jq -r '.DomainNameConfigurations[0].ApiGatewayDomainName')

echo "   API Gateway domain: ${API_GW_DOMAIN}"

# 5. Create API mapping
echo "5. Creating API mapping"
aws apigatewayv2 create-api-mapping \
    --domain-name "${DOMAIN_NAME}" \
    --api-id "${API_ID}" \
    --stage '$default' \
    --region "${REGION}" >/dev/null 2>&1 || echo "   Mapping already exists"

echo "   ✓ Mapping created"

echo ""
echo "=== Custom Domain Setup Complete ==="
echo ""
echo "Add this DNS record to pauseai.info:"
echo ""
echo "  Type: CNAME"
echo "  Name: collagen"
echo "  Value: ${API_GW_DOMAIN}"
echo "  TTL: 300"
echo ""
echo "After DNS propagates, test:"
echo "  https://collagen.pauseai.info/t/test_prototype/abc12345/validate"
