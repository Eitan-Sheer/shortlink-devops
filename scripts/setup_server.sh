#!/bin/bash
# Exit immediately if a command exits with a non-zero status
# Treat unset variables as an error
# Fail a pipeline if any command fails
set -euo pipefail

APP_NAME="shortlink"
APP_USER="shortlink"
APP_GROUP="shortlink"

# Paths
OPT_DIR="/opt/${APP_NAME}"
ETC_DIR="/etc/${APP_NAME}"
LOG_DIR="/var/log/${APP_NAME}"
ENV_FILE="${ETC_DIR}/${APP_NAME}.env"

echo "Starting server setup for ${APP_NAME}..."

# 1. Create Group (Idempotent: check if exists first)
if getent group "${APP_GROUP}" > /dev/null 2>&1; then
    echo "Group ${APP_GROUP} already exists."
else
    echo "Creating group ${APP_GROUP}..."
    groupadd --system "${APP_GROUP}"
fi

# 2. Create User (Idempotent: check if exists first)
if id "${APP_USER}" > /dev/null 2>&1; then
    echo "User ${APP_USER} already exists."
else
    echo "Creating user ${APP_USER}..."
    useradd --system --gid "${APP_GROUP}" --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
fi

# 3. Create Directories
echo "Creating directories..."
mkdir -p "${OPT_DIR}"
mkdir -p "${ETC_DIR}"
mkdir -p "${LOG_DIR}"

# 4. Set Ownership and Permissions
echo "Setting permissions..."
# /opt is owned by root, but the app dir needs to be accessible by the app user
chown -R "${APP_USER}:${APP_GROUP}" "${OPT_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${LOG_DIR}"

# The /etc dir is owned by root, but the group can read it
chown -R root:"${APP_GROUP}" "${ETC_DIR}"
chmod 750 "${ETC_DIR}"

# 5. Create the secrets file securely
if [ ! -f "${ENV_FILE}" ]; then
    echo "Creating environment file at ${ENV_FILE}..."
    touch "${ENV_FILE}"
    # Generate a dummy password for now (we'll change this later)
    echo "DB_PASSWORD=super_secret_placeholder" > "${ENV_FILE}"
fi

# Set 640 permissions: root (owner) can rw, shortlink (group) can read, others can do nothing.
chown root:"${APP_GROUP}" "${ENV_FILE}"
chmod 640 "${ENV_FILE}"

echo "Server setup completed successfully!"