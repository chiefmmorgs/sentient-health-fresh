# E2B Custom Sandbox Template with S3 Integration

This directory contains the files needed to create a custom E2B sandbox template with automatic S3 integration via goofys.

## Files

- `e2b.Dockerfile` - Custom E2B template definition
- `startup.sh` - Automatic S3 mounting script
- `README.md` - This documentation

## Template Features

✅ **S3 Auto-mounting** - Automatically mounts S3 bucket to `/home/user/bucket`  
✅ **goofys + s3fs** - High-performance S3 filesystem with fallback  
✅ **Data Analysis Stack** - Pre-installed pandas, numpy, matplotlib, etc.  
✅ **Workspace Symlinks** - Easy access via `/workspace/data`, `/workspace/results`  
✅ **Production Ready** - Zero manual configuration required  

## Quick Setup

### 1. Run SentientResearchAgent Setup

The main setup script handles everything automatically:

```bash
# From project root
./setup.sh
```

Choose either Docker or Native setup. The setup script will automatically:
- ✅ Install E2B CLI
- ✅ Authenticate with E2B (using API key from .env)
- ✅ Build custom template 'sentient-e2b-s3'
- ✅ Configure all dependencies

### 2. Configure Environment Variables

Update your `.env` file with the required credentials:

```bash
E2B_API_KEY=your_e2b_api_key
E2B_TEMPLATE_ID=sentient-e2b-s3
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your-bucket-name
AWS_REGION=us-east-1
```

**That's it!** No additional manual steps required.

## Usage in SentientResearchAgent

### Using agno E2BTools directly

```python
from agno.tools.e2b import E2BTools

# Create toolkit with custom template
toolkit = E2BTools(template="sentient-e2b-s3")

# Execute code with automatic S3 sync
result = toolkit.run_python_code('''
import pandas as pd
import matplotlib.pyplot as plt

# Your data analysis
df = pd.read_csv("/workspace/data/input.csv")
result = df.groupby("category").sum()

# Save to S3 (automatic sync via goofys)
result.to_parquet("/workspace/results/analysis.parquet")
plt.savefig("/workspace/results/plot.png")
''')
```

### Agent Configuration

```yaml
# agents.yaml
toolkits:
  - name: "E2BTools"
    adapter_class: "agno.tools.e2b.E2BTools"
    config:
      template: "sentient-e2b-s3"
      timeout: 300
```

## S3 Mount Points

The custom template automatically creates these mount points:

| Sandbox Path | S3 Path | Purpose |
|-------------|---------|---------|
| `/home/user/bucket/` | `s3://bucket/` | Root S3 mount |
| `/workspace/data/` | `s3://bucket/data/` | Input data |
| `/workspace/results/` | `s3://bucket/results/` | Analysis results |
| `/workspace/outputs/` | `s3://bucket/outputs/` | Generated files |

## File Synchronization

- **Automatic**: Files saved to mounted paths are automatically synced to S3 when closed (goofys close-to-open consistency)
- **No manual sync needed**: Just save files to the mounted directories
- **Immediate availability**: Files appear in S3 immediately after file close operation

## Troubleshooting

### Template Build Issues

```bash
# Check E2B authentication
e2b auth whoami

# Rebuild template
e2b template build -n sentient-e2b-s3 --force
```

### S3 Mount Issues

Check sandbox logs for mount status:

```python
toolkit.run_python_code('''
import os
print("S3 mount status:", os.path.ismount("/home/user/bucket"))
print("S3 contents:", os.listdir("/home/user/bucket") if os.path.exists("/home/user/bucket") else "Not mounted")
''')
```

### AWS Credentials

Ensure AWS credentials have proper S3 permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::your-bucket-name",
                "arn:aws:s3:::your-bucket-name/*"
            ]
        }
    ]
}
```

## Production Deployment

For production environments:

1. **Use the setup.sh Docker option** for containerized deployment
2. **Use IAM roles** instead of access keys when possible
3. **Enable S3 versioning** for data protection
4. **Monitor S3 costs** - goofys can generate many API calls
5. **Set appropriate timeouts** for long-running analyses
6. **Use separate S3 buckets** for different environments (dev/staging/prod)

## Integration with SentientResearchAgent

The E2B template integrates seamlessly with SentientResearchAgent:

1. **Automatic Discovery**: Environment variables are automatically passed to sandboxes
2. **Docker Compose**: Full integration with existing docker-compose.yml
3. **Setup Script**: Use `./setup.sh` to configure everything
4. **Agent Configuration**: Simply specify the custom template in agents.yaml

## Performance Notes

- **goofys**: Preferred for performance, uses HTTP/2
- **s3fs**: Fallback option, more compatible but slower
- **Cache settings**: Optimized for data analysis workloads
- **File operations**: Sequential writes perform best

## Security Considerations

- AWS credentials are stored in sandbox memory only
- S3 access limited to specified bucket
- Sandbox isolation prevents cross-contamination
- Automatic credential cleanup on sandbox termination