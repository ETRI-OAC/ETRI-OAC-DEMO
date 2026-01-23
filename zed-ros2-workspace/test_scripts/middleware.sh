#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(cd "${SCRIPT_DIR}/../openpath-CANINE-middleware" && pwd)"
BUILD_DIR="$(cd "${PARENT_DIR}/build/" && pwd)"

if [ -d "${BUILD_DIR}" ]; then
    echo "CANINE middleware build folder path : $BUILD_DIR"
    cd ${BUILD_DIR}
    cd "lib/Console"
else
    echo "Build folder is not found."
    echo "Make build folder."
    cd ${PARENT_DIR}
    mkdir "build"
    BUILD_DIR="$(cd "${PARENT_DIR}/build/" && pwd)"
    cd ${BUILD_DIR}
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make
    cd "lib/Console"
fi

./canine_middleware
