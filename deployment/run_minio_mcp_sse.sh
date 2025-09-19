#!/bin/bash

# Exit on error
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║           MinIO MCP SSE Server Launcher              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# Get the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}📁 Project Directory: $PROJECT_DIR${NC}"
echo -e "${CYAN}🚀 Script Directory: $SCRIPT_DIR${NC}"
echo ""

# Check if virtual environment exists
VENV_PATH="/home/csle/minio/minio-api-dev"
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}❌ Error: Virtual environment not found at $VENV_PATH${NC}"
    echo -e "${YELLOW}Please ensure the virtual environment is created and activated.${NC}"
    exit 1
fi

# Check if .env file exists
ENV_FILE="$PROJECT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Error: .env file not found at $ENV_FILE${NC}"
    echo -e "${YELLOW}Please ensure .env file exists in the project root.${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Environment file found: $ENV_FILE${NC}"

# Extract configuration from .env file
KEYCLOAK_URL=$(grep "KEYCLOAK_SERVER_URL" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d ' ')
MINIO_API_URL=$(grep "MINIO_API_BASE_URL" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d ' ')
SSE_PORT=$(grep "MCP_SSE_PORT" "$ENV_FILE" | cut -d '=' -f2 | tr -d '"' | tr -d ' ')

# Set defaults if not found
KEYCLOAK_URL=${KEYCLOAK_URL:-"https://keycloak.example.com"}
MINIO_API_URL=${MINIO_API_URL:-"https://minio.example.com"}
SSE_PORT=${SSE_PORT:-"8765"}

echo -e "${CYAN}🔧 Configuration:${NC}"
echo -e "   Keycloak URL: $KEYCLOAK_URL"
echo -e "   MinIO API URL: $MINIO_API_URL"
echo -e "   SSE Port: $SSE_PORT"
echo ""

# Check if Keycloak is accessible (optional)
echo -e "${GREEN}🔍 Checking Keycloak server accessibility...${NC}"
if curl -s -f "$KEYCLOAK_URL/realms/master" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Keycloak server is accessible!${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Keycloak server may not be accessible at $KEYCLOAK_URL${NC}"
    echo -e "${YELLOW}   This may cause authentication issues.${NC}"
fi

# Check if MinIO API is accessible (optional)
echo -e "${GREEN}🔍 Checking MinIO API server accessibility...${NC}"
if curl -s -f "$MINIO_API_URL/health" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ MinIO API server is accessible!${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: MinIO API server may not be accessible at $MINIO_API_URL${NC}"
    echo -e "${YELLOW}   This may cause API operation issues.${NC}"
fi

# Check if port is already in use
echo -e "${GREEN}🔍 Checking if port $SSE_PORT is available...${NC}"
if lsof -Pi :$SSE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}❌ Error: Port $SSE_PORT is already in use!${NC}"
    echo -e "${YELLOW}Please stop the service using this port or change MCP_SSE_PORT in .env${NC}"
    echo -e "${CYAN}To see what's using the port: lsof -i :$SSE_PORT${NC}"
    exit 1
else
    echo -e "${GREEN}✅ Port $SSE_PORT is available!${NC}"
fi

echo ""
echo -e "${GREEN}🚀 Starting MinIO MCP SSE Server...${NC}"
echo -e "${YELLOW}📡 Server will be available at:${NC}"
echo -e "   • Local:    http://127.0.0.1:$SSE_PORT"
echo -e "   • External: http://$(hostname -I | awk '{print $1}'):$SSE_PORT"
echo -e "${YELLOW}🔗 This server uses standard MCP SSE protocol${NC}"
echo -e "${YELLOW}📱 Compatible with MCP clients (Langflow, Claude Desktop, etc.)${NC}"
echo ""
echo -e "${CYAN}💡 Quick Start:${NC}"
echo -e "   1. Connect your MCP client to the server URL above"
echo -e "   2. Use 'minio_login' tool to authenticate first"
echo -e "   3. Try 'minio_health_check' to verify connectivity"
echo -e "   4. Explore 35 available MinIO management tools"
echo ""
echo -e "${BLUE}🔄 Press Ctrl+C to stop the server${NC}"
echo -e "${BLUE}────────────────────────────────────────────────────────${NC}"

# Activate virtual environment and run the server
cd "$SCRIPT_DIR"
source "$VENV_PATH/bin/activate"

# Export environment variables for the Python script
export PYTHONPATH="$PROJECT_DIR:$PYTHONPATH"

# Run the MCP SSE server
python minio_mcp_sse_server.py
