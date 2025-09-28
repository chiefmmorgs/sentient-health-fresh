#!/bin/bash
# Startup script for E2B sandbox optimized for general code execution and data analysis
# This script runs when the sandbox is created

# Note: Don't use 'set -e' as it can interfere with E2B's process management

echo "🚀 Starting Sentient E2B Sandbox for code execution and data analysis..."

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# # Start Jupyter Server
function start_jupyter_server() {
	counter=0
	response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8888/api/status")
	while [[ ${response} -ne 200 ]]; do
		let counter++
		if ((counter % 20 == 0)); then
			echo "Waiting for Jupyter Server to start..."
			sleep 0.1
		fi

		response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8888/api/status")
	done

	cd /root/.server/
	/root/.server/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 49999 --workers 1 --no-access-log --no-use-colors --timeout-keep-alive 640
}

# Setup AWS credentials if environment variables are available
setup_aws_credentials() {
    if [ ! -z "$AWS_ACCESS_KEY_ID" ] && [ ! -z "$AWS_SECRET_ACCESS_KEY" ]; then
        log "Setting up AWS credentials..."
        
        # Create s3fs password file in /root as per E2B documentation
        echo "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" > /root/.passwd-s3fs
        chmod 600 /root/.passwd-s3fs
        
        # Also create in user home for goofys compatibility
        echo "$AWS_ACCESS_KEY_ID:$AWS_SECRET_ACCESS_KEY" > $HOME/.passwd-s3fs
        chmod 600 $HOME/.passwd-s3fs
        
        # Setup AWS CLI credentials in user's home
        mkdir -p $HOME/.aws
        cat > $HOME/.aws/credentials << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF
        
        # Also create AWS credentials in /root for system access
        mkdir -p /root/.aws
        cat > /root/.aws/credentials << EOF
[default]
aws_access_key_id = $AWS_ACCESS_KEY_ID
aws_secret_access_key = $AWS_SECRET_ACCESS_KEY
EOF
        
        if [ ! -z "$AWS_REGION" ]; then
            cat > $HOME/.aws/config << EOF
[default]
region = $AWS_REGION
output = json
EOF
            cat > /root/.aws/config << EOF
[default]
region = $AWS_REGION
output = json
EOF
        fi
        
        log "✅ AWS credentials configured in /root and $HOME"
    else
        log "⚠️  AWS credentials not found in environment variables"
    fi
}

# Mount S3 bucket using configurable mount directory
mount_s3_bucket() {
    if [ ! -z "$S3_BUCKET_NAME" ] && [ -f /root/.passwd-s3fs ]; then
        # Get mount directory from environment variable or use default
        MOUNT_DIR="${S3_MOUNT_DIR:-/opt/sentient}"
        
        log "Mounting S3 bucket: $S3_BUCKET_NAME to $MOUNT_DIR"
        
        # Create mount point at configurable directory
        mkdir -p "$MOUNT_DIR"
        
        # Use goofys as primary S3 mounting tool (better performance)
        log "Attempting to mount with goofys..."
        log "AWS Region: ${AWS_REGION:-us-east-1}"
        
        # Try goofys with auto-region detection (let goofys find the correct region)
        log "Attempting goofys mount with auto-region detection for bucket: $S3_BUCKET_NAME"
        if goofys \
            --stat-cache-ttl=10s \
            --type-cache-ttl=10s \
            --dir-mode=0777 \
            --file-mode=0666 \
            -o allow_other \
            $S3_BUCKET_NAME "$MOUNT_DIR"; then
            
            log "✅ S3 bucket mounted successfully with goofys"
            echo "goofys" > /tmp/mount-method
            
            # Set proper permissions for user access
            chown -R user:user "$MOUNT_DIR" 2>/dev/null || true
            
        else
            # Fallback to s3fs if goofys fails
            log "goofys failed, checking syslog for details..."
            # Check syslog for goofys errors
            if command -v journalctl &> /dev/null; then
                log "Recent goofys errors from journalctl:"
                journalctl -n 20 | grep -i goofys || log "No goofys entries in journalctl"
            fi
            if [ -f /var/log/syslog ]; then
                log "Recent goofys errors from syslog:"
                tail -50 /var/log/syslog | grep -i goofys || log "No goofys entries in syslog"
            fi
            if [ -f /var/log/messages ]; then
                log "Recent goofys errors from messages:"
                tail -50 /var/log/messages | grep -i goofys || log "No goofys entries in messages"
            fi
            log "Trying s3fs..."
            log "Using s3fs with credentials file /root/.passwd-s3fs"
            if s3fs -o allow_other,passwd_file=/root/.passwd-s3fs,url=https://s3.${AWS_REGION:-us-east-1}.amazonaws.com $S3_BUCKET_NAME "$MOUNT_DIR"; then
                log "✅ S3 bucket mounted successfully with s3fs"
                echo "s3fs" > /tmp/mount-method
                
                # Set proper permissions for user access
                chown -R user:user "$MOUNT_DIR" 2>/dev/null || true
            else
                log "⚠️  Both goofys and s3fs failed - S3 mounting not available"
                echo "failed" > /tmp/mount-method
                # Don't fail the startup - continue without S3
            fi
        fi
        
        # Verify mount and setup workspace structure
        # Use multiple methods to verify S3 mount (FUSE mounts don't always show with mountpoint)
        if mountpoint -q "$MOUNT_DIR" || mount | grep -q "$MOUNT_DIR" || [ -d "$MOUNT_DIR" ] && timeout 5 ls "$MOUNT_DIR" >/dev/null 2>&1; then
            # Additional verification: ensure this is the expected bucket by writing and listing via AWS CLI
            if command -v aws >/dev/null 2>&1; then
                test_file="$MOUNT_DIR/.sentient-mount-test-$(date +%s)-$$"
                echo "mount-check" > "$test_file" 2>/dev/null || true
                sleep 1
                test_key=$(basename "$test_file")
                if aws s3 ls "s3://$S3_BUCKET_NAME/$test_key" >/dev/null 2>&1; then
                    log "✅ S3 mount verification successful for bucket s3://$S3_BUCKET_NAME"
                    rm -f "$test_file" 2>/dev/null || true
                else
                    log "❌ Mounted directory does not reflect bucket s3://$S3_BUCKET_NAME"
                fi
            else
                log "⚠️  AWS CLI not available; skipping bucket verification"
            fi
            
            # Create shared workspace structure in S3
            mkdir -p "$MOUNT_DIR"/shared 2>/dev/null || true
        else
            log "❌ S3 mount verification failed"
            log "Debug info:"
            log "- Directory exists: $([ -d "$MOUNT_DIR" ] && echo 'yes' || echo 'no')"
            log "- Mountpoint check: $(mountpoint -q "$MOUNT_DIR" && echo 'mounted' || echo 'not mounted')"
            log "- Mount output: $(mount | grep "$MOUNT_DIR" || echo 'no mount found')"
            log "- Directory listing test: $(timeout 2 ls "$MOUNT_DIR" 2>/dev/null | wc -l) items"
        fi
        
    else
        log "⚠️  S3 bucket name or AWS credentials not configured"
    fi
}

# Main startup sequence
main() {
    log "Initializing E2B sandbox..."
    
    # Setup AWS credentials and mount S3 bucket
    setup_aws_credentials
    mount_s3_bucket
    
    # Create essential workspace directory
    mkdir -p /workspace 2>/dev/null || true
    
    log "✅ Startup script completed successfully"
}

# Run main function
main "$@"

echo "Starting Code Interpreter server..."
start_jupyter_server &
MATPLOTLIBRC=/root/.config/matplotlib/.matplotlibrc jupyter server --IdentityProvider.token="" >/dev/null 2>&1