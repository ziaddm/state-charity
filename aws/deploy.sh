#!/bin/bash
# AWS Deployment Script
# Run this to deploy the entire application to AWS

set -e

# Configuration
STACK_NAME="compliance-analytics-prod"
REGION="us-east-1"
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "🚀 Starting AWS deployment for Compliance Analytics"
echo "Stack Name: $STACK_NAME"
echo "Region: $REGION"
echo "AWS Account: $AWS_ACCOUNT_ID"
echo ""

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS CLI not configured. Run 'aws configure' first."
    exit 1
fi

# Prompt for secrets
read -p "Enter DATABASE_URL: " DATABASE_URL
read -sp "Enter SECRET_KEY: " SECRET_KEY
echo ""
read -p "Enter SMTP_USER: " SMTP_USER
read -sp "Enter SMTP_PASSWORD: " SMTP_PASSWORD
echo ""

# Deploy CloudFormation stack
echo "📦 Deploying CloudFormation stack..."
aws cloudformation deploy \
    --template-file cloudformation-template.yml \
    --stack-name $STACK_NAME \
    --region $REGION \
    --parameter-overrides \
        Environment=production \
        DatabaseURL="$DATABASE_URL" \
        SecretKey="$SECRET_KEY" \
        SMTPUser="$SMTP_USER" \
        SMTPPassword="$SMTP_PASSWORD" \
    --capabilities CAPABILITY_IAM \
    --no-fail-on-empty-changeset

echo "✅ CloudFormation stack deployed"

# Get outputs
ECR_REPO=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='BackendRepositoryURI'].OutputValue" \
    --output text)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
    --output text)

BACKEND_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
    --output text)

echo ""
echo "📝 Stack outputs:"
echo "Backend ECR: $ECR_REPO"
echo "Frontend S3: $FRONTEND_BUCKET"
echo "Backend URL: $BACKEND_URL"
echo ""

# Build and push backend Docker image
echo "🐳 Building and pushing backend Docker image..."
cd ../compliance-backend

# Login to ECR
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_REPO

# Build and push
docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest

echo "✅ Backend image pushed to ECR"

# Update ECS service
echo "🔄 Updating ECS service..."
aws ecs update-service \
    --cluster ${STACK_NAME}-cluster \
    --service ${STACK_NAME}-backend-service \
    --force-new-deployment \
    --region $REGION > /dev/null

echo "✅ ECS service updated"

# Build and deploy frontend
echo "🎨 Building frontend..."
cd ../compliance-frontend

# Install dependencies
npm ci

# Build with backend URL
VITE_API_URL=$BACKEND_URL npm run build

echo "☁️  Uploading to S3..."
aws s3 sync dist/ s3://$FRONTEND_BUCKET/ --delete

# Get CloudFront distribution ID
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Origins.Items[0].DomainName=='$FRONTEND_BUCKET.s3.amazonaws.com'].Id" \
    --output text)

if [ ! -z "$DISTRIBUTION_ID" ]; then
    echo "🔄 Invalidating CloudFront cache..."
    aws cloudfront create-invalidation \
        --distribution-id $DISTRIBUTION_ID \
        --paths "/*" > /dev/null
    echo "✅ CloudFront cache invalidated"
fi

# Get final URLs
CLOUDFRONT_URL=$(aws cloudformation describe-stacks \
    --stack-name $STACK_NAME \
    --region $REGION \
    --query "Stacks[0].Outputs[?OutputKey=='CloudFrontURL'].OutputValue" \
    --output text)

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "📍 Your application URLs:"
echo "Frontend: https://$CLOUDFRONT_URL"
echo "Backend API: $BACKEND_URL"
echo ""
echo "⚠️  Note: ECS service is starting. It may take 2-3 minutes for the backend to be fully available."
echo "You can monitor the service status in the AWS ECS console."
