#!/bin/bash

# Start clients for all worktrees in parallel
echo "Starting clients for all worktrees..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Start client in interview-dashboard-1 (port 5174)
echo -e "${BLUE}Starting client in interview-dashboard-1 on port 5174...${NC}"
cd trees/interview-dashboard-1/client && bun run dev &
PID1=$!
echo -e "${GREEN}✓ interview-dashboard-1 client started (PID: $PID1)${NC}"

# Start client in interview-dashboard-2 (port 5175)
echo -e "${BLUE}Starting client in interview-dashboard-2 on port 5175...${NC}"
cd trees/interview-dashboard-2/client && bun run dev &
PID2=$!
echo -e "${GREEN}✓ interview-dashboard-2 client started (PID: $PID2)${NC}"

# Start client in interview-dashboard-3 (port 5176)
echo -e "${BLUE}Starting client in interview-dashboard-3 on port 5176...${NC}"
cd trees/interview-dashboard-3/client && bun run dev &
PID3=$!
echo -e "${GREEN}✓ interview-dashboard-3 client started (PID: $PID3)${NC}"

echo -e "\n${YELLOW}All clients started!${NC}"
echo -e "${YELLOW}Access them at:${NC}"
echo -e "  ${GREEN}http://localhost:5174${NC} - interview-dashboard-1"
echo -e "  ${GREEN}http://localhost:5175${NC} - interview-dashboard-2"
echo -e "  ${GREEN}http://localhost:5176${NC} - interview-dashboard-3"
echo -e "\n${YELLOW}Press Ctrl+C to stop all clients${NC}"

# Wait for any of the processes to exit
wait $PID1 $PID2 $PID3
