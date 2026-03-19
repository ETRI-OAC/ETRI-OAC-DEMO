#!/bin/bash
cd $(dirname $0)

if [ "$#" -lt 1 ]; then
    # Use default versions when not provided
    ZED_SDK_DEFAULT="zedsdk-4.2.3"
    CUDA_DEFAULT="cu126"
    echo "No ZED SDK version provided, using defaults:"
    echo "  ZED_SDK_VERSION=${ZED_SDK_DEFAULT}"
    echo "  CUDA_VERSION=${CUDA_DEFAULT}"
    set -- "$ZED_SDK_DEFAULT" "$CUDA_DEFAULT"
fi

ZED_SDK_version=$1
CUDA_VERSION=${2:-cu126}

# Check if the first arg is a custom URL
CUSTOM_ZED_SDK_URL=$1
# Use curl to check if the URL is valid (returns HTTP 200)
if [ "$(curl -L -I "${CUSTOM_ZED_SDK_URL}" -o /dev/null -s -w '%{http_code}\n' | head -n 1)" = "200" ]; then
    echo "${ZED_SDK_version} detected as a valid custom installer URL"

    echo "Building dockerfile with a custom ZED SDK URL"

    docker build -t zed_ros2_ubuntu24_sdk_custom \
    --build-arg CUSTOM_ZED_SDK_URL=$CUSTOM_ZED_SDK_URL \
    --build-arg CUDA_VERSION=$CUDA_VERSION \
    -f ./Dockerfile.ubuntu-jazzy .
else
    # Verify the ZED SDK format (digits.digits.digits)
    if ! [[ $1 =~ ^zedsdk-[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
        echo "Invalid ZED SDK version format. Expected: zedsdk-X.Y.Z"
        exit 1
    fi

    # Remove the prefix 'zedsdk-'
    zed_sdk_version_number="${ZED_SDK_version#zedsdk-}"

    # Split the string and assign to variables
    IFS='.' read -r sdk_major sdk_minor sdk_patch <<< "$zed_sdk_version_number"

    echo "Building dockerfile for Ubuntu 24.04 with ZED SDK $1 and CUDA $CUDA_VERSION"

    docker build -t zed_ros2_ubuntu24_sdk_${sdk_major}.${sdk_minor}.${sdk_patch} \
    --build-arg ZED_SDK_MAJOR=$sdk_major \
    --build-arg ZED_SDK_MINOR=$sdk_minor \
    --build-arg ZED_SDK_PATCH=$sdk_patch \
    --build-arg CUDA_VERSION=$CUDA_VERSION \
    -f ./Dockerfile.ubuntu-jazzy .
fi
