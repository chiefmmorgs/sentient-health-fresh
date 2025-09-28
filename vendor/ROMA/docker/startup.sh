#!/usr/bin/env bash

# startup.sh - Container entrypoint for SentientResearchAgent backend
#
# This script optionally mounts an S3 bucket into the container using `goofys`
# before launching the application. All configuration is done via environment
# variables so that the same image can run with or without the S3 mount.
#
# Required environment variables when S3 mounting is enabled (S3_MOUNT_ENABLED=true):
#   - S3_BUCKET_NAME   : Name of the S3 bucket to mount.
#   - S3_MOUNT_DIR     : Absolute path inside the container where the bucket should be mounted.
#
# Optional environment variables:
#   - S3_MOUNT_ENABLED : (default: false) If set to "true", the script attempts to mount the bucket.
#   - AWS_REGION       : AWS region for the bucket (fallback to AWS_DEFAULT_REGION).
#   - GOOFYS_EXTRA_ARGS: Additional flags passed verbatim to `goofys`.
#
# The remainder of this script execs whatever command is provided as arguments,
# allowing Docker's CMD to specify the application start-up command.

set -euo pipefail

info() {
  echo "[startup.sh] $*"
}

error_exit() {
  echo "[startup.sh] ERROR: $*" >&2
  exit 1
}

# Return 0 if the path appears mounted using multiple strategies
is_path_mounted() {
  local mount_dir="$1"
  # Strategy 1: mountpoint utility (most reliable)
  if mountpoint -q "$mount_dir" 2>/dev/null; then
    return 0
  fi
  # Strategy 2: scan /proc/mounts
  if grep -q " $mount_dir " /proc/mounts 2>/dev/null; then
    return 0
  fi
  # Strategy 3: findmnt if available
  if command -v findmnt >/dev/null 2>&1; then
    if findmnt -n -T "$mount_dir" >/dev/null 2>&1; then
      return 0
    fi
  fi
  return 1
}

# Emit mount details for a path for debugging and classification
describe_mount() {
  local mount_dir="$1"
  if command -v findmnt >/dev/null 2>&1; then
    local mount_info=$(findmnt -n -o FSTYPE,SOURCE,TARGET -T "$mount_dir" 2>/dev/null || true)
    if [ -n "$mount_info" ]; then
      info "findmnt: $mount_info"
    fi
  fi
  local mount_line=$(mount | grep " $mount_dir " || true)
  if [ -n "$mount_line" ]; then
    info "mount: $mount_line"
  fi
}

# Verify that a mounted directory corresponds to the expected S3 bucket
# Returns 0 when verified, 1 otherwise. Never exits the script.
# Strategy:
# 1) Check /proc/mounts for device name patterns like goofys#<bucket> or s3fs#<bucket>
# 2) Fallback: write a temp file and confirm via AWS CLI that it appears in the bucket
verify_bucket_mount() {
  local mount_dir="$1"
  local bucket="$2"

  # Method 1: Inspect mount table (Linux)
  if [ -r /proc/mounts ]; then
    if awk -v b="$bucket" -v m="$mount_dir" '
      $2==m && ($1 ~ /^goofys#/ || $1 ~ /^s3fs#/) {
        if (index($1, "#" b) > 0) { found=1 }
      }
      END { exit(found?0:1) }
    ' /proc/mounts; then
      info "Mount table confirms device maps to bucket s3://${bucket}"
      return 0
    fi
  fi

  # Method 2: AWS CLI verification (requires credentials)
  if command -v aws >/dev/null 2>&1; then
    local test_file="${mount_dir}/.sentient-mount-test-$(date +%s)-$$"
    if ! echo "mount-check" > "${test_file}"; then
      info "Could not write test file to ${mount_dir} for verification"
      return 1
    fi
    sleep 1
    local test_key
    test_key=$(basename "${test_file}")
    if aws s3 ls "s3://${bucket}/${test_key}" >/dev/null 2>&1; then
      info "AWS CLI confirms mount points to s3://${bucket}"
      rm -f "${test_file}" || true
      return 0
    fi
    # Cleanup if listing failed as well
    rm -f "${test_file}" || true
    return 1
  fi

  info "AWS CLI not available; skipping bucket verification"
  return 0
}

# Mount an S3 bucket with goofys at the given directory and verify
mount_s3_with_goofys() {
  local bucket="$1"
  local mount_dir="$2"

  mkdir -p "${mount_dir}" || error_exit "Failed to create mount directory ${mount_dir}"

  local GOOFYS_ARGS=("${GOOFYS_EXTRA_ARGS:-}" "${bucket}" "${mount_dir}")
  info "Running: goofys ${GOOFYS_ARGS[*]}"
  goofys ${GOOFYS_EXTRA_ARGS:-} "${bucket}" "${mount_dir}" &

  # Ensure mount succeeded
  sleep 2
  mountpoint -q "${mount_dir}" || error_exit "Goofys mount failed for ${mount_dir}"

  # Verify correctness
  if ! verify_bucket_mount "${mount_dir}" "${bucket}"; then
    error_exit "Mounted directory does not reflect bucket s3://${bucket}"
  fi
  info "Successfully mounted s3://${bucket} to ${mount_dir}"
}

S3_MOUNT_ENABLED="${S3_MOUNT_ENABLED:-false}"
S3_MOUNT_DIR="${S3_MOUNT_DIR:-/opt/sentient}"

if [[ "${S3_MOUNT_ENABLED}" == "true" ]]; then
  # Validate required variables
  : "${S3_BUCKET_NAME:?S3_BUCKET_NAME must be set when S3_MOUNT_ENABLED=true}"

  info "S3 mounting enabled. Checking for host-mounted S3..."
  
  # Check if directory is already mounted and accessible
  if is_path_mounted "${S3_MOUNT_DIR}"; then
    info "Detected existing mount at ${S3_MOUNT_DIR}"
    describe_mount "${S3_MOUNT_DIR}"
    
    # Check if this looks like a host bind mount
    if mount | grep -q "${S3_MOUNT_DIR}.*fakeowner"; then
      info "Host bind mount detected - assuming host has mounted S3"
      
      # Verify the mount content if possible
      if verify_bucket_mount "${S3_MOUNT_DIR}" "${S3_BUCKET_NAME}"; then
        info "Host S3 mount verified for bucket s3://${S3_BUCKET_NAME}"
      else
        info "Host mount exists - proceeding (verification may fail for bind mounts)"
      fi
      
      # List contents to confirm accessibility
      if ls "${S3_MOUNT_DIR}" >/dev/null 2>&1; then
        file_count=$(ls -1 "${S3_MOUNT_DIR}" | wc -l)
        info "S3 directory accessible with ${file_count} items"
      fi
      
    else
      # This might be a container-mounted S3, verify it
      if verify_bucket_mount "${S3_MOUNT_DIR}" "${S3_BUCKET_NAME}"; then
        info "Existing S3 mount verified for bucket s3://${S3_BUCKET_NAME}"
      else
        info "Existing mount verification failed - may need remounting"
      fi
    fi
    
  else
    info "No existing mount detected at ${S3_MOUNT_DIR}"
    info "Note: If using host-based mounting, ensure 'setup.sh --docker' was run first"
    
    # Fallback: attempt container-based mounting
    info "Attempting fallback container-based S3 mounting..."
    mount_s3_with_goofys "${S3_BUCKET_NAME}" "${S3_MOUNT_DIR}"
  fi
  
  info "S3 setup complete:"
  info "  - S3 directory: ${S3_MOUNT_DIR}"
  info "  - Expected bucket: s3://${S3_BUCKET_NAME}"
  info "  - Application can read/write to ${S3_MOUNT_DIR}"
  info "  - Files should be visible on host (if host-mounted)"
else
  info "S3 mounting disabled. Skipping S3 setup."
fi

# Hand over control to the CMD provided in Dockerfile / docker-compose
exec "$@"

