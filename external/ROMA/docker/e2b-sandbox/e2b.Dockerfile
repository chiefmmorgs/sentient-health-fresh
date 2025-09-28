# Custom E2B Sandbox Template with S3 Integration
# Base image is required - only Debian-based images are supported
FROM e2bdev/code-interpreter:latest

# Accept build arguments for AWS credentials and S3 mounting configuration
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY
ARG AWS_REGION=us-west-2
ARG S3_BUCKET_NAME
ARG S3_MOUNT_DIR=/opt/sentient

# Set environment variables from build args
ENV AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
ENV AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
ENV AWS_REGION=${AWS_REGION}
ENV S3_BUCKET_NAME=${S3_BUCKET_NAME}
ENV S3_MOUNT_DIR=${S3_MOUNT_DIR}

# Update package list
RUN apt-get update

# Install only essential S3 filesystem tools
RUN apt-get install -y \
    s3fs \
    awscli \
    curl \
    fuse \
    jq \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Install goofys for high-performance S3 mounting
RUN curl -L https://github.com/kahing/goofys/releases/latest/download/goofys -o /usr/local/bin/goofys \
    && chmod +x /usr/local/bin/goofys

# Copy requirements file
COPY requirements.txt /tmp/requirements.txt

# Install additional packages not pre-installed in E2B code interpreter
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# Create only essential directories
RUN mkdir -p /workspace

# Set up proper permissions for FUSE
RUN echo "user_allow_other" >> /etc/fuse.conf

# Copy startup script to the same location as the official E2B template
COPY start-up.sh /root/.jupyter/start-up.sh

# Make script executable for all users
RUN chmod +x /root/.jupyter/start-up.sh

# Note: E2B will run startup.sh via the start_cmd in e2b.toml
# No systemd setup needed - E2B handles container initialization differently

# Set workspace as working directory  
WORKDIR /workspace