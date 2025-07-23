#!/bin/bash

# Intentional Computing App Runner
# This script resolves conda environment issues with macOS app bundles

echo "=== Intentional Computing App Runner ==="

# Check if we're in conda environment
if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
    echo "Warning: Conda environment detected ($CONDA_DEFAULT_ENV)"
    echo "This may cause bundle signature issues on macOS"
    echo ""
fi

# Try to use system Python first
SYSTEM_PYTHON="/usr/bin/python3"
if [[ -f "$SYSTEM_PYTHON" ]]; then
    echo "Using system Python: $SYSTEM_PYTHON"
    
    # Check if required packages are installed in system Python
    echo "Checking system Python dependencies..."
    
    # Install dependencies if needed
    $SYSTEM_PYTHON -m pip install --user -r requirements.txt
    
    # Run the app with system Python
    echo "Starting app with system Python..."
    $SYSTEM_PYTHON main.py
else
    echo "System Python not found. Trying alternative solutions..."
    
    # Method 2: Create a proper app bundle structure
    echo "Creating temporary app bundle structure..."
    
    # Create Info.plist for proper bundle identification
    cat > /tmp/Info.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>com.intentionalcomputing.app</string>
    <key>CFBundleName</key>
    <string>IntentionalComputing</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF
    
    # Set bundle info
    export PYTHONPATH="$PWD:$PYTHONPATH"
    export NSAppTransportSecurity='{"NSAllowsArbitraryLoads":true}'
    
    # Run with conda Python but with bundle info
    echo "Starting app with bundle configuration..."
    python main.py
fi 