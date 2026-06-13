# AWS Deployment Files

## Quick Deploy

```bash
chmod +x deploy.sh
./deploy.sh
```

## What's Included

- **`cloudformation-template.yml`** - Complete AWS infrastructure definition
  - Creates VPC, subnets, security groups
  - Sets up ECS Fargate cluster
  - Configures Application Load Balancer
  - Creates S3 buckets for frontend and uploads
  - Sets up CloudFront CDN
  - Configures ECR for Docker images
  - Creates Secrets Manager for credentials

- **`deploy.sh`** - Automated deployment script
  - Deploys CloudFormation stack
  - Builds and pushes Docker images
  - Deploys backend to ECS
  - Builds and deploys frontend to S3/CloudFront

## Manual Commands

### Check Deployment Status
```bash
aws cloudformation describe-stacks \
  --stack-name compliance-analytics-prod \
  --query 'Stacks[0].StackStatus'
```

### View Application URLs
```bash
aws cloudformation describe-stacks \
  --stack-name compliance-analytics-prod \
  --query 'Stacks[0].Outputs'
```

### View ECS Logs
```bash
aws logs tail /ecs/compliance-analytics-prod --follow
```

### Update Backend
```bash
# Build and push new image
ECR_REPO=$(aws cloudformation describe-stacks \
  --stack-name compliance-analytics-prod \
  --query "Stacks[0].Outputs[?OutputKey=='BackendRepositoryURI'].OutputValue" \
  --output text)

cd ../compliance-backend
docker build -t $ECR_REPO:latest .
docker push $ECR_REPO:latest

# Force ECS to deploy new version
aws ecs update-service \
  --cluster compliance-analytics-prod-cluster \
  --service compliance-analytics-prod-backend-service \
  --force-new-deployment
```

### Update Frontend
```bash
# Get backend URL
BACKEND_URL=$(aws cloudformation describe-stacks \
  --stack-name compliance-analytics-prod \
  --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" \
  --output text)

# Build and deploy
cd ../compliance-frontend
npm run build
VITE_API_URL=$BACKEND_URL npm run build

BUCKET=$(aws cloudformation describe-stacks \
  --stack-name compliance-analytics-prod \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" \
  --output text)

aws s3 sync dist/ s3://$BUCKET/ --delete
```

## Cost Optimization

### Scale Down for Development
```bash
# Reduce to 0 tasks (stop backend)
aws ecs update-service \
  --cluster compliance-analytics-prod-cluster \
  --service compliance-analytics-prod-backend-service \
  --desired-count 0

# Scale back up
aws ecs update-service \
  --cluster compliance-analytics-prod-cluster \
  --service compliance-analytics-prod-backend-service \
  --desired-count 1
```

## Cleanup

```bash
# Delete stack (removes most resources)
aws cloudformation delete-stack \
  --stack-name compliance-analytics-prod

# Manually delete S3 buckets
aws s3 rb s3://compliance-analytics-prod-frontend-[account-id] --force
aws s3 rb s3://compliance-analytics-prod-uploads-[account-id] --force
```

## Troubleshooting

### Deployment Failed
```bash
# Check stack events
aws cloudformation describe-stack-events \
  --stack-name compliance-analytics-prod \
  --max-items 20
```

### Backend Not Starting
```bash
# Check ECS service
aws ecs describe-services \
  --cluster compliance-analytics-prod-cluster \
  --services compliance-analytics-prod-backend-service

# Check logs
aws logs tail /ecs/compliance-analytics-prod --follow
```

### Frontend 404 Errors
```bash
# Verify S3 contents
aws s3 ls s3://[frontend-bucket]/ --recursive

# Invalidate CloudFront
DISTRIBUTION_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[0].Id" \
  --output text)

aws cloudfront create-invalidation \
  --distribution-id $DISTRIBUTION_ID \
  --paths "/*"
```

## Security Notes

- **Never commit** `.env.production` with real credentials
- Use **AWS Secrets Manager** for production secrets
- Enable **MFA** on AWS account
- Rotate **access keys** regularly
- Review **IAM permissions** periodically

## Support

For detailed instructions, see:
- [../AWS_DEPLOYMENT_GUIDE.md](../AWS_DEPLOYMENT_GUIDE.md) - Full guide
- [../README_DEPLOYMENT.md](../README_DEPLOYMENT.md) - Quick start
