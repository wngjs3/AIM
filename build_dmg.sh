#!/bin/bash

# Intention App DMG Builder
# Supports 3 versions: BASIC, REMINDER, FULL
# Usage: ./build_dmg.sh [basic|reminder|full|all]

# Create build_assets directory if it doesn't exist
mkdir -p build_assets

# Generate DMG background image
echo "Generating DMG background image..."
python create_dmg_background.py

# App configurations
MODES=("BASIC" "REMINDER" "FULL")
NAMES=("Orange(new)" "Blue(new)" "Purple(new)")
SHORT_NAMES=("Orange(new)" "Blue(new)" "Purple(new)")
BUNDLE_IDS=("com.app.orange.new.app" "com.app.blue.new.app" "com.app.purple.new.app")
ICONS=("3.png" "2.png" "1.png")
RECORDING_ICONS=("3_recording.png" "2_recording.png" "1_recording.png")

CONSTANTS_FILE="src/config/constants.py"
APP_FILE="src/app.py"

# Function to clean previous builds
clean_builds() {
    echo "Cleaning previous build files..."
    if [ -d "dist" ]; then
        echo "Removing existing dist directory..."
        rm -rf dist
    fi
    
    if [ -d "build" ]; then
        echo "Removing existing build directory..."
        rm -rf build
    fi
    
    # Remove installed app versions
    echo "Removing any installed app versions from /Applications..."
    sudo rm -rf "/Applications/Purple(new).app" 2>/dev/null
    sudo rm -rf "/Applications/Blue(new).app" 2>/dev/null
    sudo rm -rf "/Applications/Orange(new).app" 2>/dev/null
    
    # Reset app permissions cache
    echo "Resetting app permissions cache..."
    tccutil reset All com.app.purple.new.app 2>/dev/null
    tccutil reset All com.app.blue.new.app 2>/dev/null
    tccutil reset All com.app.orange.new.app 2>/dev/null
    
    # Clean __pycache__ directories
    echo "Cleaning __pycache__ directories..."
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
}

# Function to backup original files
backup_files() {
    mkdir -p temp_configs
    cp "$CONSTANTS_FILE" "temp_configs/constants_backup.py"
    cp "$APP_FILE" "temp_configs/app_backup.py"
}

# Function to restore original files
restore_files() {
    cp "temp_configs/constants_backup.py" "$CONSTANTS_FILE"
    cp "temp_configs/app_backup.py" "$APP_FILE"
    rm -rf temp_configs
}

# Function to build a specific app version
build_app() {
    local index=$1
    local mode=${MODES[$index]}
    local name=${NAMES[$index]}
    local short_name=${SHORT_NAMES[$index]}
    local bundle_id=${BUNDLE_IDS[$index]}
    local icon=${ICONS[$index]}
    local recording_icon=${RECORDING_ICONS[$index]}
    
    echo "---------------------------------------------"
    echo "Building $name ($mode mode)..."
    echo "---------------------------------------------"
    
    # Modify constants file for this mode
    sed -i '' "s/^APP_MODE = APP_MODE_[A-Z]*$/APP_MODE = APP_MODE_$mode/" "$CONSTANTS_FILE"
    
    # Set icon paths
    echo "Setting icon paths for $name..."
    export ICON_PATH="src/assets/$icon"
    export RECORDING_ICON_PATH="src/assets/$recording_icon"
    
    # Update app.py for menu bar name
    echo "Updating app.py for $name..."
    sed -i '' "s/name=\"[^\"]*\"/name=\"$short_name\"/" "$APP_FILE"
    
    # Set environment variables
    export APP_NAME="$name"
    export BUNDLE_ID="$bundle_id"
    
    # Clear caches
    echo "Clearing macOS app caches..."
    find ~/Library/Caches -name "com.app.*" -exec rm -rf {} \; 2>/dev/null
    
    # Build the app
    echo "Building $name..."
    python setup.py py2app
    
    # Build the DMG
    APP_VERSION=$(python -c "import src.config.constants as c; print(c.APP_VERSION)")
    echo "Building DMG file for $name..."
    
    mkdir -p dist
    dmgbuild -s dmgbuild_settings.py "$name" "dist/$name-v$APP_VERSION.dmg"
    
    # Clean for next build
    rm -rf build
    
    echo "✅ $name DMG created successfully!"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [basic|reminder|full|all]"
    echo ""
    echo "Options:"
    echo "  basic    - Build only Orange(new) (BASIC mode)"
    echo "  reminder - Build only Blue(new) (REMINDER mode)"
    echo "  full     - Build only Purple(new) (FULL mode)"
    echo "  all      - Build all 3 versions"
    echo ""
    echo "App Mode Mapping:"
    echo "  Purple(new) -> FULL (treatment)"
    echo "  Blue(new) -> REMINDER (control)"
    echo "  Orange(new) -> BASIC (baseline)"
}

# Main execution
case "$1" in
    "basic")
        echo "=== Building BASIC version only ==="
        clean_builds
        backup_files
        build_app 0
        restore_files
        echo "✅ BASIC version build complete!"
        ;;
    "reminder")
        echo "=== Building REMINDER version only ==="
        clean_builds
        backup_files
        build_app 1
        restore_files
        echo "✅ REMINDER version build complete!"
        ;;
    "full")
        echo "=== Building FULL version only ==="
        clean_builds
        backup_files
        build_app 2
        restore_files
        echo "✅ FULL version build complete!"
        ;;
    "all"|"")
        echo "=== Building all 3 versions ==="
        echo "Purple(new) -> FULL (treatment)"
        echo "Blue(new) -> REMINDER (control)"
        echo "Orange(new) -> BASIC (baseline)"
        echo "=========================="
        
        clean_builds
        backup_files
        
        # Build all versions
        for i in "${!MODES[@]}"; do
            build_app $i
        done
        
        restore_files
        
        echo ""
        echo "🎉 All DMG files created in dist/ directory"
        echo "빌드가 완료되었습니다. 각 앱을 새로 설치하여 사용하세요."
        echo ""
        echo "=== 생성된 파일들 ==="
        ls -la dist/*.dmg 2>/dev/null || echo "No DMG files found"
        ;;
    *)
        show_usage
        exit 1
        ;;
esac

echo ""
echo "=== App Mode Mapping ==="
echo "Purple(new) -> FULL (treatment)"
echo "Blue(new) -> REMINDER (control)"
echo "Orange(new) -> BASIC (baseline)"
echo "========================="