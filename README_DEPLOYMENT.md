# Compliance Analytics - Quick Deployment Guide

## What Was Set Up

Your application is now ready to deploy to AWS with the following architecture:

```
Frontend (React) → CloudFront + S3
Backend (FastAPI) → ECS Fargate + ALB
Database → PostgreSQL (Supabase or RDS)
```

## Files Created

### Docker Configuration
- `compliance-backend/Dockerfile` - Backend container definition
- `compliance-frontend/Dockerfile` - Frontend container definition
- `docker-compose.yml` - Local development stack
- `.dockerignore` files - Optimize build performance

### AWS Infrastructure
- `aws/cloudformation-template.yml` - Complete AWS infrastructure as code
- `aws/deploy.sh` - One-command deployment script

### CI/CD
- `.github/workflows/deploy.yml` - Automated deployment on git push

### Configuration
- `.env.production` - Production environment template
- `compliance-backend/app/main.py` - Updated with dynamic CORS
- `.gitignore` - Updated to exclude secrets

### Documentation
- `AWS_DEPLOYMENT_GUIDE.md` - Complete deployment walkthrough

## Quick Start - Deploy to AWS

### Prerequisites (5 minutes)
```bash
# 1. Install AWS CLI
brew install awscli  # macOS
# or download from https://aws.amazon.com/cli/

# 2. Configure AWS
aws configure
# Enter your AWS Access Key ID and Secret Access Key

# 3. Install Docker
# Download from https://docker.com
```

### Deploy (10 minutes)
```bash
# Navigate to AWS folder
cd aws

# Make script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will ask for:
- Database URL (your Supabase connection string)
- Secret key (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- SMTP credentials (Gmail app password)

**That's it!** In 10-15 minutes you'll get two URLs:
- Frontend: `https://[id].cloudfront.net`
- Backend: `http://[id].us-east-1.elb.amazonaws.com`

## Test Locally First

```bash
# Start entire stack locally
docker-compose up --build

# Access at:
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Set Up Auto-Deployment (Optional)

### Add GitHub Secrets:
1. Go to your repo → Settings → Secrets → Actions
2. Add:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

Now every push to `main` automatically deploys to AWS!

## Costs

**~$40-60/month** for production usage:
- ECS Fargate: $15-25
- Load Balancer: $16
- S3 + CloudFront: $1-5
- Misc: $5-15

Free tier covers first 12 months for many services.

## Need Help?

Read the full guide: [AWS_DEPLOYMENT_GUIDE.md](./AWS_DEPLOYMENT_GUIDE.md)

Common issues:
- **Docker not running**: Start Docker Desktop
- **AWS credentials**: Run `aws configure`
- **Deployment failed**: Check CloudWatch logs

## Architecture Diagram

```
User
 │
 ├─▶ CloudFront (CDN)
 │    └─▶ S3 (React App)
 │
 └─▶ ALB (Load Balancer)
      └─▶ ECS Fargate (FastAPI)
           └─▶ PostgreSQL (Supabase/RDS)
```

## What's Next?

After deployment:
1. ✅ Set up custom domain (Route 53)
2. ✅ Enable HTTPS with ACM certificate
3. ✅ Configure email notifications
4. ✅ Set up monitoring alerts
5. ✅ Enable auto-scaling

Happy deploying! 🚀
