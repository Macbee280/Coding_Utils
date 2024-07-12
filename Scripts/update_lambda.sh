#!/bin/bash

# Function to perform full deployment
aws_build() {
    # Input Parameters
    ENVIRONMENT=$1
    AWS_REGISTRY=$2
    AWS_ACCESS_KEY_ID=$3
    AWS_SECRET_ACCESS_KEY=$4
    GITHUB_USERNAME=$5
    GITHUB_TOKEN=$6
    LAMBDA_NAME=$7

    # Validate Input Parameters
    if [ -z "$ENVIRONMENT" ] || [ -z "$AWS_REGISTRY" ] || [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ -z "$GITHUB_USERNAME" ] || [ -z "$GITHUB_TOKEN" ] || [ -z "$LAMBDA_NAME" ]; then
        echo "Usage: $0 <environment> <aws_registry> <aws_access_key_id> <aws_secret_access_key> <github_username> <github_token> <lambda_name>"
        exit 1
    fi

    # Generate a random ID
    RANDOM_ID=$(openssl rand -hex 5)

    # Pull previous image, tag with random ID, and push
    if docker pull "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous"; then
        docker tag "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous" "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:${RANDOM_ID}"
        docker push "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:${RANDOM_ID}"
        docker rmi "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:${RANDOM_ID}"
    else
        echo "Failed to pull previous image. Continuing without tagging and pushing."
    fi

    # Pull latest image, tag with previous, and push
    docker pull "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest"
    docker tag "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest" "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous"
    docker push "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous"
    docker rmi "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous"

    # Build latest image with AWS credentials as build args and push
    docker build --build-arg AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID}" --build-arg AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY}" --build-arg GITHUB_USERNAME="${GITHUB_USERNAME}" --build-arg GITHUB_TOKEN="${GITHUB_TOKEN}" -t "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest" .
    docker push "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest"
    docker rmi "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest"

    echo "Build completed successfully."
}

# Function to perform rollback
aws_rollback() {
    # Input Parameters
    ENVIRONMENT=$1
    AWS_REGISTRY=$2
    LAMBDA_NAME=$3

    # Validate Input Parameters
    if [ -z "$ENVIRONMENT" ] || [ -z "$AWS_REGISTRY" ] || [ -z "$LAMBDA_NAME" ]; then
        echo "Usage: $0 <environment> <aws_registry> <lambda_name>"
        exit 1
    fi

    # Rollback to previous image
    docker pull "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous"
    docker tag "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:previous" "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest"
    docker push "${AWS_REGISTRY}/${LAMBDA_NAME}-${ENVIRONMENT}:latest"

    echo "Rollback completed successfully."
}

# Main script starts here
if [ $# -lt 7 ] || [ $# -gt 8 ]; then
    echo "Usage: $0 <environment> <aws_registry> <aws_access_key_id> <aws_secret_access_key> <github_username> <github_token> <lambda_name> [rollback]"
    exit 1
fi

case "$8" in
    rollback)
        aws_rollback "$1" "$2" "$7"
        ;;
    *)
        aws_build "$@"
        ;;
esac
