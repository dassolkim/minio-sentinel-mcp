#!/bin/bash

# MinIO MCP SSE Server Connection Test Script

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SSE_PORT=${MCP_SSE_PORT:-8765}
SERVER_IP=$(hostname -I | awk '{print $1}')

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         MinIO MCP SSE Connection Test                ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

echo -e "${YELLOW}🔍 Testing MinIO MCP SSE Server Connection${NC}"
echo -e "Server IP: $SERVER_IP"
echo -e "Port: $SSE_PORT"
echo ""

# Test 1: Check if port is listening
echo -e "${BLUE}Test 1: Port Listening Check${NC}"
if lsof -Pi :$SSE_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Port $SSE_PORT is listening${NC}"
else
    echo -e "${RED}❌ Port $SSE_PORT is not listening${NC}"
    echo -e "${YELLOW}Please start the MCP SSE server first${NC}"
    exit 1
fi

# Test 2: Local connection test
echo -e "${BLUE}Test 2: Local Connection Test${NC}"
if timeout 5 bash -c "</dev/tcp/127.0.0.1/$SSE_PORT" 2>/dev/null; then
    echo -e "${GREEN}✅ Local connection successful${NC}"
else
    echo -e "${RED}❌ Local connection failed${NC}"
fi

# Test 3: External connection test (if different from local)
if [ "$SERVER_IP" != "127.0.0.1" ]; then
    echo -e "${BLUE}Test 3: External Connection Test${NC}"
    if timeout 5 bash -c "</dev/tcp/$SERVER_IP/$SSE_PORT" 2>/dev/null; then
        echo -e "${GREEN}✅ External connection successful${NC}"
    else
        echo -e "${RED}❌ External connection failed${NC}"
        echo -e "${YELLOW}Check firewall settings:${NC}"
        echo -e "  sudo ufw allow $SSE_PORT"
        echo -e "  sudo firewall-cmd --add-port=$SSE_PORT/tcp --permanent"
    fi
fi

# Test 4: Process check
echo -e "${BLUE}Test 4: Process Check${NC}"
if pgrep -f "minio_mcp_sse_server" > /dev/null; then
    echo -e "${GREEN}✅ MCP SSE server process is running${NC}"
    echo -e "${YELLOW}Process details:${NC}"
    ps aux | grep minio_mcp_sse_server | grep -v grep
else
    echo -e "${RED}❌ MCP SSE server process not found${NC}"
fi

# Test 5: Network binding check
echo -e "${BLUE}Test 5: Network Binding Check${NC}"
if netstat -tlnp 2>/dev/null | grep ":$SSE_PORT " | grep -q "0.0.0.0:$SSE_PORT"; then
    echo -e "${GREEN}✅ Server is bound to 0.0.0.0 (external access enabled)${NC}"
elif netstat -tlnp 2>/dev/null | grep ":$SSE_PORT " | grep -q "127.0.0.1:$SSE_PORT"; then
    echo -e "${YELLOW}⚠️  Server is bound to 127.0.0.1 (local only)${NC}"
    echo -e "${YELLOW}For external access, server should bind to 0.0.0.0${NC}"
else
    echo -e "${RED}❌ Unable to determine server binding${NC}"
fi

echo ""
echo -e "${BLUE}📋 Connection Information:${NC}"
echo -e "Local URL:    http://127.0.0.1:$SSE_PORT"
echo -e "External URL: http://$SERVER_IP:$SSE_PORT"
echo ""

echo -e "${BLUE}💡 For MCP Clients (Langflow, etc.):${NC}"
echo -e "Use the External URL for remote connections"
echo -e "Use the Local URL for same-machine connections"
echo ""

echo -e "${GREEN}Test completed!${NC}"
