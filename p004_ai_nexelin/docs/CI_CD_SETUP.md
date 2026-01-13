# CI/CD Setup Documentation

## Overview

This project uses GitHub Actions for Continuous Integration and Continuous Deployment (CI/CD). The CI/CD pipeline is triggered on pushes to the `main` branch and includes comprehensive checks, security scanning, testing, and automated deployment.

## Workflow Structure

### 1. Frontend CI/CD (`frontend-ci-cd.yml`)

**Triggers:**
- Push to `main` branch (changes in `MASTER/client_portal/**`)
- Pull requests to `main` branch

**Jobs:**
1. **Lint and Format Check**
   - ESLint validation
   - TypeScript type checking
   - Code formatting verification

2. **Security Scan**
   - npm audit for vulnerable dependencies
   - Security report generation

3. **Build**
   - Production build creation
   - Build artifact archiving
   - Build size verification

4. **Deploy to FTP**
   - Automatic deployment to FTP server
   - Deployment verification
   - Error logging

5. **Archive Deployment**
   - Deployment artifact archiving (90 days retention)

### 2. Backend CI/CD (`backend-ci-cd.yml`)

**Triggers:**
- Push to `main` branch (changes in `MASTER/**`, `requirements.txt`, Dockerfiles)
- Pull requests to `main` branch

**Jobs:**
1. **Code Quality Checks**
   - Black formatting check
   - isort import sorting
   - Flake8 linting
   - Pylint analysis

2. **Security Scan**
   - Bandit security scanning
   - Safety dependency check
   - pip-audit vulnerability scanning

3. **Database Migrations Check**
   - Migration file validation
   - Missing migrations detection

4. **Run Tests**
   - Unit and integration tests
   - Test coverage reporting
   - PostgreSQL and Redis service testing

5. **Build Docker Image**
   - Docker image building
   - Image caching
   - Image archiving

6. **Deploy to VPS**
   - SSH-based deployment
   - Docker container management
   - Database migrations
   - Static files collection
   - Health checks

7. **Archive Deployment**
   - Deployment metadata archiving (90 days retention)

### 3. Pre-Deployment Checks (`pre-deployment-checks.yml`)

**Triggers:**
- Push to `main` branch
- Pull requests to `main` branch

**Jobs:**
1. **System Health Checks**
   - Docker Compose validation
   - Python syntax checking
   - Requirements.txt validation
   - Critical files verification

2. **Dependency Check**
   - Outdated dependencies detection
   - Security vulnerability scanning

3. **Configuration Validation**
   - Django settings validation
   - Database migration checks

### 4. Error Logging (`error-logging.yml`)

**Triggers:**
- Workflow completion (success or failure)
- Workflow failure

**Jobs:**
1. **Log Workflow Errors**
   - Error log collection
   - Error report generation
   - Artifact archiving (90 days retention)

## Required GitHub Secrets

### Frontend Deployment Secrets

```bash
FTP_SERVER=ftp.yourdomain.com
FTP_USERNAME=your_ftp_username
FTP_PASSWORD=your_ftp_password
FTP_REMOTE_DIR=/public_html/
VITE_API_BASE_URL=https://api.yourdomain.com
```

### Backend Deployment Secrets

```bash
VPS_HOST=your.vps.ip.address
VPS_USER=deploy_user
VPS_SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----...
DOCKER_REGISTRY=registry.yourdomain.com  # Optional
DOCKER_USERNAME=docker_username  # Optional
DOCKER_PASSWORD=docker_password  # Optional
DOCKER_IMAGE_NAME=ai-nexelin-backend
```

### How to Add Secrets

1. Go to your GitHub repository
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its value

## Local Testing

### Test Frontend Workflow Locally

```bash
# Install act (GitHub Actions local runner)
# macOS: brew install act
# Linux: https://github.com/nektos/act#installation

# Run frontend workflow
act -W .github/workflows/frontend-ci-cd.yml push

# Run with secrets
act -W .github/workflows/frontend-ci-cd.yml push --secret FTP_SERVER=your_server
```

### Test Backend Workflow Locally

```bash
# Run backend workflow
act -W .github/workflows/backend-ci-cd.yml push

# Run with secrets
act -W .github/workflows/backend-ci-cd.yml push \
  --secret VPS_HOST=your_host \
  --secret VPS_USER=your_user
```

## Deployment Process

### Frontend Deployment Flow

1. **Code Push** → Push to `main` branch
2. **Linting** → ESLint and TypeScript checks
3. **Security Scan** → npm audit
4. **Build** → Production build creation
5. **Deploy** → FTP upload
6. **Archive** → Deployment artifact storage

### Backend Deployment Flow

1. **Code Push** → Push to `main` branch
2. **Code Quality** → Black, Flake8, Pylint
3. **Security Scan** → Bandit, Safety, pip-audit
4. **Migrations Check** → Database migration validation
5. **Tests** → Unit and integration tests
6. **Docker Build** → Docker image creation
7. **Deploy** → VPS deployment via SSH
8. **Archive** → Deployment metadata storage

## Monitoring and Logs

### View Workflow Logs

1. Go to **Actions** tab in GitHub repository
2. Select the workflow run
3. Click on individual jobs to view logs
4. Download artifacts for detailed reports

### Error Reports

Error reports are automatically generated and archived when workflows fail:
- Location: Workflow artifacts
- Retention: 90 days
- Format: Markdown summaries + log files

## Troubleshooting

### Common Issues

#### Frontend Deployment Fails

**Issue:** FTP connection timeout
- **Solution:** Check FTP server credentials and firewall settings
- **Check:** Verify `FTP_SERVER`, `FTP_USERNAME`, `FTP_PASSWORD` secrets

**Issue:** Build fails
- **Solution:** Check Node.js version compatibility
- **Check:** Review build logs for dependency issues

#### Backend Deployment Fails

**Issue:** SSH connection fails
- **Solution:** Verify SSH key format and permissions
- **Check:** Ensure `VPS_SSH_PRIVATE_KEY` is correctly formatted

**Issue:** Docker build fails
- **Solution:** Check Dockerfile syntax and dependencies
- **Check:** Review build logs for missing dependencies

**Issue:** Migration fails
- **Solution:** Check database connection and migration files
- **Check:** Verify database credentials and schema

### Debugging Steps

1. **Check Workflow Logs**
   - Navigate to Actions → Failed workflow → Job logs

2. **Verify Secrets**
   - Ensure all required secrets are set
   - Check secret values are correct

3. **Test Locally**
   - Run workflows locally with `act`
   - Test deployment scripts manually

4. **Check Dependencies**
   - Verify all dependencies are up to date
   - Check for breaking changes

## Security Considerations

### Secret Management

- Never commit secrets to repository
- Use GitHub Secrets for sensitive data
- Rotate secrets regularly
- Use least privilege principle

### Security Scanning

- Bandit scans Python code for security issues
- Safety checks Python dependencies
- npm audit checks Node.js dependencies
- All reports are archived for review

### Code Quality

- All code must pass linting checks
- Type checking is enforced
- Code formatting is standardized
- Security vulnerabilities block deployment

## Best Practices

1. **Always test locally** before pushing to `main`
2. **Review security reports** before deployment
3. **Monitor deployment logs** for errors
4. **Keep dependencies updated** regularly
5. **Document changes** in commit messages
6. **Use feature branches** for development
7. **Review PRs** before merging to `main`

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Documentation](https://docs.docker.com/)
- [Django Deployment Guide](https://docs.djangoproject.com/en/stable/howto/deployment/)

