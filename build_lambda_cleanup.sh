#!/bin/bash

# Move into the directory where this script is located
cd "$(dirname "$0")" || exit

# Define the paths for the output and build directories
BUILD_DIR="temp_build_dir"

# Cleanup of the build directory
rm -rf "$BUILD_DIR"
