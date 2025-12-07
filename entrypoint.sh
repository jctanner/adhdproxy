#!/bin/bash

CERT_DIR="/app/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"

# Create certs directory if it doesn't exist
mkdir -p "$CERT_DIR"

# Generate self-signed certificate if it doesn't exist
if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
    echo "Generating self-signed SSL certificate..."
    openssl req -x509 -newkey rsa:4096 -nodes \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -days 365 \
        -subj "/C=US/ST=State/L=City/O=ADHDProxy/CN=localhost"
    echo "Certificate generated successfully"
else
    echo "Using existing SSL certificate"
fi

# Start the Flask app
exec python flaskapp.py
