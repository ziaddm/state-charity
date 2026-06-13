# AWS Deployment Guide

Complete guide for deploying the Compliance Analytics application to AWS.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                            │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐           ┌──────────────────────┐        │
│  │              │           │                      │        │
│  │  CloudFront  │─────────▶│  S3 Bucket          │        │
│  │  (CDN)       │           │  (Frontend)         │        │
│  │              │           │                      │        │
│  └──────────────┘           └──────────────────────┘        │
│        │                                                     │
│        │                                                     │
│        ▼                                                     │
│  ┌──────────────┐           ┌──────────────────────┐        │
│  │              │           │                      │        │
│  │  ALB         │─────────▶│  ECS Fargate        │        │
│  │  (Load       │           │  (Backend API)      │        │
│  │   Balancer)  │           │                      │        │
│  │              │           │  ┌────────────────┐ │        │
│  └──────────────┘           │  │ FastAPI        │ │        │
│                             │  │ Container      │ │        │
│                             │  └────────────────┘ │        │
│                             └──────────┬───────────┘        │
│                                        │                     │
│                                        ▼                     │
│                             ┌──────────────────────┐        │
│                             │                      │        │
│                             │  PostgreSQL          │        │
│                             │  (Supabase/RDS)     │        │
│                             │                      │        │
│                             └──────────────────────┘        │
│                                                               │
│  ┌──────────────────────────────────────────────┐          │
│  │  Secrets Manager (Credentials)               │          │
│  │  CloudWatch (Logs & Monitoring)              │          │
│  │  ECR (Container Registry)                    │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

## Cost Estimate

**Monthly costs (light usage):**
- ECS Fargate: ~$15-25/month (1 task, 0.5 vCPU, 1GB RAM)
- Application Load Balancer: ~$16/month
- S3 + CloudFront: ~$1-5/month
- Secrets Manager: ~$0.40/month
- CloudWatch Logs: ~$2-5/month
- Data Transfer: ~$5-10/month

**Total: ~$40-60/month** for production workload

## Prerequisites

### 1. AWS Account Setup
- Create an AWS account at https://aws.amazon.com
- Set up billing alerts (recommended: $50/month threshold)
- Enable MFA on root account

### 2. Install AWS CLI (Windows)

**Option A: Using MSI Installer (Recommended)**
1. Download AWS CLI installer: https://awscli.amazonaws.com/AWSCLIV2.msi
2. Run the downloaded MSI installer
3. Follow the installation wizard

**Option B: Using Command Line**
```cmd
REM If you have Chocolatey installed:
choco install awscli
```

### 3. Configure AWS CLI
```cmd
aws configure

REM Enter when prompted:
REM AWS Access Key ID: [Your access key]
REM AWS Secret Access Key: [Your secret key]
REM Default region: us-east-1
REM Default output format: json
```

### 4. Install Docker Desktop for Windows
1. Download from https://www.docker.com/products/docker-desktop
2. Install Docker Desktop
3. Restart your computer if prompted
4. Ensure Docker Desktop is running (check system tray)

### 5. Install Git for Windows (if not already installed)
1. Download from https://git-scm.com/download/win
2. Run the installer
3. Use default settings (Git Bash will be included)

## Deployment Methods

You have **two options** for deploying to AWS:

### Option A: Manual Deployment (Recommended for Windows)
Deploy each component step-by-step using AWS Console and CMD commands.

### Option B: Automated PowerShell Deployment (Advanced)
Use PowerShell scripts to automate the deployment.

---

## Option A: Manual Deployment (Windows CMD)

### Step 1: Prepare Your Environment

1. **Get your database credentials**
   - If using Supabase, get your connection string from the Supabase dashboard
   - Format: `postgresql://user:password@host:port/database`

2. **Generate a secret key**
   ```cmd
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Get SMTP credentials** (for email)
   - Gmail: Create an app password at https://myaccount.google.com/apppasswords
   - Or use another SMTP provider

### Step 2: Verify AWS CLI Installation

```cmd
REM Check AWS CLI is installed
aws --version

REM Check AWS credentials are configured
aws sts get-caller-identity
```

### Step 3: Verify Deployment

```cmd
REM Check ECS service status
aws ecs describe-services --cluster compliance-analytics-prod-cluster --services compliance-analytics-prod-backend-service

REM Check CloudFormation stack
aws cloudformation describe-stacks --stack-name compliance-analytics-prod
```

### Step 4: Access Your Application

The script outputs two URLs:
- **Frontend**: `https://[cloudfront-id].cloudfront.net`
- **Backend API**: `http://[alb-dns].us-east-1.elb.amazonaws.com`

Visit the frontend URL in your browser!

---

## Step-by-Step AWS Deployment (Windows)

### Step 1: Create Secrets in AWS Secrets Manager

1. Go to **AWS Secrets Manager** in the AWS Console (https://console.aws.amazon.com/secretsmanager/)
2. Click **Store a new secret**
3. Choose **Other type of secret**
4. Add key-value pairs:
   ```
   DATABASE_URL: postgresql://...
   SECRET_KEY: your-secret-key
   SMTP_USER: your-email@gmail.com
   SMTP_PASSWORD: your-app-password
   ```
5. Name it: `compliance-analytics-prod-secrets`
6. Click **Store**

### Step 2: Deploy CloudFormation Stack

1. Go to **AWS CloudFormation** in the AWS Console (https://console.aws.amazon.com/cloudformation/)
2. Click **Create stack** → **With new resources**
3. Upload the template file: `aws\cloudformation-template.yml`
4. Fill in parameters:
   - Stack name: `compliance-analytics-prod`
   - DatabaseURL: Your PostgreSQL connection string
   - SecretKey: Your generated secret key
   - SMTPUser: Your email
   - SMTPPassword: Your SMTP password
5. Check **I acknowledge that AWS CloudFormation might create IAM resources**
6. Click **Create stack**
7. Wait ~10 minutes for creation to complete

### Step 3: Build and Push Backend Docker Image

```cmd
REM Get ECR repository URI from CloudFormation outputs
aws cloudformation describe-stacks --stack-name compliance-analytics-prod --query "Stacks[0].Outputs[?OutputKey=='BackendRepositoryURI'].OutputValue" --output text > ecr_repo.txt
set /p ECR_REPO=<ecr_repo.txt

REM Display the ECR repository
echo ECR Repository: %ECR_REPO%

REM Login to ECR
aws ecr get-login-password --region us-east-1 > ecr_password.txt
type ecr_password.txt | docker login --username AWS --password-stdin %ECR_REPO%
del ecr_password.txt

REM Build backend image
cd compliance-backend
docker build -t %ECR_REPO%:latest .

REM Push to ECR
docker push %ECR_REPO%:latest

REM Go back to root directory
cd ..
```

### Step 4: Update ECS Service

```cmd
REM Force new deployment with the image
aws ecs update-service --cluster compliance-analytics-prod-cluster --service compliance-analytics-prod-backend-service --force-new-deployment
```

### Step 5: Build and Deploy Frontend

```cmd
REM Get backend URL
aws cloudformation describe-stacks --stack-name compliance-analytics-prod --query "Stacks[0].Outputs[?OutputKey=='LoadBalancerURL'].OutputValue" --output text > backend_url.txt
set /p BACKEND_URL=<backend_url.txt
echo Backend URL: %BACKEND_URL%

REM Build frontend
cd compliance-frontend
call npm ci
set VITE_API_URL=%BACKEND_URL%
call npm run build

REM Get S3 bucket name
aws cloudformation describe-stacks --stack-name compliance-analytics-prod --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text > bucket_name.txt
set /p BUCKET=<bucket_name.txt
echo S3 Bucket: %BUCKET%

REM Upload to S3
aws s3 sync dist\ s3://%BUCKET%/ --delete

REM Get CloudFront distribution ID
aws cloudfront list-distributions --query "DistributionList.Items[?Origins.Items[0].DomainName=='%BUCKET%.s3.amazonaws.com'].Id" --output text > distribution_id.txt
set /p DISTRIBUTION_ID=<distribution_id.txt
echo CloudFront Distribution: %DISTRIBUTION_ID%

REM Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id %DISTRIBUTION_ID% --paths "/*"

REM Go back to root directory
cd ..

REM Clean up temporary files
del backend_url.txt bucket_name.txt distribution_id.txt ecr_repo.txt
```

---

## Setting Up CI/CD with GitHub Actions

### Step 1: Create GitHub Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add the following secrets:
   - `AWS_ACCESS_KEY_ID`: Your AWS access key
   - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key

### Step 2: Push to Main Branch

The GitHub Actions workflow (`.github/workflows/deploy.yml`) will automatically:
1. Build backend Docker image
2. Push to ECR
3. Update ECS service
4. Build frontend
5. Deploy to S3
6. Invalidate CloudFront cache

Every push to `main` triggers a deployment!

---

## Local Development with Docker (Windows)

### Test the entire stack locally:

```cmd
REM Start all services
docker-compose up --build

REM Access:
REM Frontend: http://localhost:3000
REM Backend: http://localhost:8000
REM Database: localhost:5432
```

### Stop services:
```cmd
REM Stop and remove containers
docker-compose down

REM Stop and remove containers + volumes (clean slate)
docker-compose down -v
```

---

## Monitoring & Debugging (Windows)

### View ECS Logs
```cmd
REM View logs in real-time
aws logs tail /ecs/compliance-analytics-prod --follow

REM View last 100 lines
aws logs tail /ecs/compliance-analytics-prod --since 1h
```

### Check Service Health
```cmd
REM Backend health check (replace [ALB-DNS] with your ALB URL)
curl http://[ALB-DNS]/api/health

REM Frontend health check (replace [CloudFront-URL] with your CloudFront URL)
curl https://[CloudFront-URL]/health

REM Alternative using PowerShell if curl is not available
powershell -Command "Invoke-WebRequest -Uri 'http://[ALB-DNS]/api/health'"
```

### ECS Service Status
```cmd
aws ecs describe-services --cluster compliance-analytics-prod-cluster --services compliance-analytics-prod-backend-service --query "services[0].{Status:status,Running:runningCount,Desired:desiredCount}"
```

### CloudWatch Logs
- Go to **CloudWatch** in AWS Console (https://console.aws.amazon.com/cloudwatch/)
- Navigate to **Log groups** → `/ecs/compliance-analytics-prod`
- View real-time logs from your backend

---

## Updating the Application (Windows)

### Update Backend Code
```cmd
REM Make your changes, then:
git add .
git commit -m "Update backend"
git push origin main

REM GitHub Actions will automatically deploy
```

### Update Frontend Code
```cmd
REM Make your changes, then:
git add .
git commit -m "Update frontend"
git push origin main

REM GitHub Actions will automatically deploy
```

### Manual Update (without CI/CD)
```cmd
REM Re-run the deployment steps manually:
REM 1. Rebuild and push Docker image (see Step 3)
REM 2. Update ECS service (see Step 4)
REM 3. Rebuild and deploy frontend (see Step 5)
```

---

## Custom Domain Setup (Optional)

### Step 1: Register Domain
- Use Route 53 or any domain registrar (GoDaddy, Namecheap, etc.)

### Step 2: Create SSL Certificate
```cmd
REM Request certificate in ACM (us-east-1 for CloudFront)
aws acm request-certificate --domain-name compliance.yourdomain.com --validation-method DNS --region us-east-1
```

### Step 3: Update CloudFormation
- Modify `aws\cloudformation-template.yml`
- Add `Aliases` and `ViewerCertificate` to CloudFront distribution
- Add Route 53 A record pointing to CloudFront

---

## Scaling (Windows)

### Increase ECS Tasks
```cmd
REM Scale to 3 tasks
aws ecs update-service --cluster compliance-analytics-prod-cluster --service compliance-analytics-prod-backend-service --desired-count 3

REM Check current status
aws ecs describe-services --cluster compliance-analytics-prod-cluster --services compliance-analytics-prod-backend-service --query "services[0].{Running:runningCount,Desired:desiredCount}"
```

### Enable Auto-Scaling
Add to CloudFormation:
```yaml
AutoScalingTarget:
  Type: AWS::ApplicationAutoScaling::ScalableTarget
  Properties:
    MaxCapacity: 5
    MinCapacity: 1
    ResourceId: !Sub service/${ECSCluster}/${ECSService.Name}
    ScalableDimension: ecs:service:DesiredCount
    ServiceNamespace: ecs
```

---

## Troubleshooting (Windows)

### Backend not starting
```cmd
REM Check ECS logs
aws logs tail /ecs/compliance-analytics-prod --follow

REM Verify task definition
aws ecs describe-task-definition --task-definition compliance-analytics-prod-backend-task

REM Check database connectivity (test from local)
REM Use your DATABASE_URL from .env
```

### Frontend 404 errors
```cmd
REM Check S3 bucket files
aws s3 ls s3://[bucket-name]/

REM Check CloudFront distribution settings
aws cloudfront get-distribution-config --id [distribution-id]
```

### CORS errors
- Verify `FRONTEND_URL` environment variable in ECS task definition
- Check browser console (F12) for exact error
- Ensure CloudFront URL is in the allowed origins list

### High costs
```cmd
REM Check ECS task count
aws ecs describe-services --cluster compliance-analytics-prod-cluster --services compliance-analytics-prod-backend-service

REM Enable AWS Cost Explorer in console
REM https://console.aws.amazon.com/cost-management/home
```

### Docker build issues
```cmd
REM Check Docker is running
docker --version
docker ps

REM Restart Docker Desktop if needed
REM Right-click Docker Desktop icon in system tray → Restart
```

---

## Cleanup / Teardown (Windows)

### Delete Everything
```cmd
REM Get bucket names first
aws cloudformation describe-stacks --stack-name compliance-analytics-prod --query "Stacks[0].Outputs[?OutputKey=='FrontendBucketName'].OutputValue" --output text > bucket_name.txt
set /p BUCKET=<bucket_name.txt

REM Empty S3 buckets
aws s3 rm s3://%BUCKET%/ --recursive

REM Delete CloudFormation stack (removes all resources)
aws cloudformation delete-stack --stack-name compliance-analytics-prod

REM Wait for stack deletion
aws cloudformation wait stack-delete-complete --stack-name compliance-analytics-prod

REM Delete S3 buckets (do this AFTER CloudFormation deletes)
aws s3 rb s3://%BUCKET%

REM Delete ECR images
aws ecr batch-delete-image --repository-name compliance-analytics-prod-backend --image-ids imageTag=latest

REM Clean up temp files
del bucket_name.txt

echo Cleanup complete!
```

---

## Security Best Practices

1. **Enable HTTPS**: Set up ACM certificate and use HTTPS only
2. **Restrict access**: Use security groups to limit traffic
3. **Rotate secrets**: Change database passwords and secret keys regularly
4. **Enable logging**: Keep CloudWatch logs for auditing
5. **Use IAM roles**: Never hardcode AWS credentials
6. **Enable MFA**: Require multi-factor authentication for admin users
7. **Regular updates**: Keep dependencies and Docker images up to date

---

## Support

For issues:
1. Check CloudWatch logs
2. Review ECS service events
3. Verify environment variables
4. Test locally with Docker Compose first

---

## Next Steps

After deployment:
1. Set up custom domain
2. Configure email notifications
3. Enable auto-scaling
4. Set up monitoring alerts
5. Configure backups
6. Implement rate limiting
7. Add WAF for security

**Your app is now live on AWS!** 🚀
