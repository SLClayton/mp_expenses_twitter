#!/bin/bash

# Move into the directory where this script is located
cd "$(dirname "$0")" || exit

# Use the provided argument as the package name, or default to "package"
PACKAGE_NAME="${1:-package}"

# Define the paths
OUT_DIR="packages"
OUTPUT_FILENAME="$OUT_DIR/$PACKAGE_NAME.zip"
BUILD_DIR="temp_build_dir"

# Create a directory to store build
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cp -R src/* "$BUILD_DIR/"

# Install the required packages into the build directory
python3 -m pip install -r requirements.txt --target="$BUILD_DIR/"

# Ensure the output directory exists
mkdir -p "$OUT_DIR"
