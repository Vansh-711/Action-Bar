#!/bin/bash

echo "📦 Creating Toolbox V4 Distribution Zip..."

# 1. Define Paths
DIST_DIR="web/assets/downloads"
ZIP_NAME="toolbox_v4_agent.zip"

# 2. Create download directory if not exists
mkdir -p "$DIST_DIR"

# 3. Zip the contents
# We exclude the 'web' folder (since that's the website itself) and system files
zip -r "$DIST_DIR/$ZIP_NAME" . -x "web/*" -x "__pycache__/*" -x "*.DS_Store" -x "*.git/*"

echo "✅ Created $DIST_DIR/$ZIP_NAME"
echo "🌐 You can now link to this file in index.html as 'assets/downloads/$ZIP_NAME'"
