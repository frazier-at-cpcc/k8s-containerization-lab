#!/bin/bash
# setup-tools.sh — Install kubectl and eksctl in CloudShell
# These install to ~/bin which persists across CloudShell sessions.

set -euo pipefail

INSTALL_DIR="$HOME/bin"
mkdir -p "$INSTALL_DIR"

# Add ~/bin to PATH if not already there
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo 'export PATH="$HOME/bin:$PATH"' >> ~/.bashrc
    export PATH="$INSTALL_DIR:$PATH"
fi

echo "=== Installing kubectl ==="
if command -v kubectl &>/dev/null; then
    echo "kubectl already installed: $(kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1)"
else
    KUBECTL_VERSION=$(curl -L -s https://dl.k8s.io/release/stable.txt)
    curl -sLO "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
    chmod +x kubectl
    mv kubectl "$INSTALL_DIR/"
    echo "Installed kubectl $KUBECTL_VERSION"
fi

echo ""
echo "=== Installing eksctl ==="
if command -v eksctl &>/dev/null; then
    echo "eksctl already installed: $(eksctl version)"
else
    PLATFORM=$(uname -s)_amd64
    curl -sLO "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_${PLATFORM}.tar.gz"
    tar xzf "eksctl_${PLATFORM}.tar.gz" -C "$INSTALL_DIR"
    rm -f "eksctl_${PLATFORM}.tar.gz"
    echo "Installed eksctl $(eksctl version)"
fi

echo ""
echo "=== Verification ==="
kubectl version --client --short 2>/dev/null || kubectl version --client 2>/dev/null | head -1
eksctl version
echo ""
echo "Tools installed to $INSTALL_DIR (persists across CloudShell sessions)."
echo "If 'kubectl' or 'eksctl' are not found, run: source ~/.bashrc"
