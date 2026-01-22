# A script for building the docker image

set -e

# Get directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# Change to the appropriate Dockerfile directory
cd "$DIR/zed_env"

# Build the Docker image
docker build -t "zed-env:l4t-r36.4" .

echo "Successfully built zed-env:l4t-r36.4"
