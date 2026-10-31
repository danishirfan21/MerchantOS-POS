#!/usr/bin/env bash
set -euo pipefail
install_dir="${RUNNER_TEMP:?}/merchantos-trivy"
mkdir -p "$install_dir"
curl --fail --location --silent --show-error --retry 3 https://github.com/aquasecurity/trivy/releases/download/v0.76.1/trivy_0.76.1_Linux-64bit.tar.gz -o "$install_dir/trivy.tar.gz"
(cd "$install_dir" && echo 'c7cbe3137fb8a48a17574bede3dd6beb16742d1e9772929940fc90082c39d9c0  trivy.tar.gz' | sha256sum --check && tar -xzf trivy.tar.gz trivy)
echo "TRIVY_PATH=$install_dir/trivy" >> "$GITHUB_ENV"
