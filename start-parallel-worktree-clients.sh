#!/bin/bash

# Script to create and run multiple worktrees for testing ThermoWorks BBQ monitoring application
echo "Starting parallel worktrees for testing..."

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Default starting port
BASE_PORT=8080

# Default admin credentials
DEFAULT_ADMIN_EMAIL="admin@grill-stats.lab.apj.dev"
DEFAULT_ADMIN_PASSWORD="admin1234"
DEFAULT_ADMIN_NAME="Administrator"

# Parse command line arguments
SPECIFIED_WORKTREES=()
EXCLUDE_WORKTREES=()
SKIP_DEPS=0
CREATE_ADMIN=1

while [[ $# -gt 0 ]]; do
  case $1 in
    --port)
      BASE_PORT="$2"
      shift 2
      ;;
    --include)
      SPECIFIED_WORKTREES+=("$2")
      shift 2
      ;;
    --exclude)
      EXCLUDE_WORKTREES+=("$2")
      shift 2
      ;;
    --skip-deps)
      SKIP_DEPS=1
      shift
      ;;
    --admin-email)
      DEFAULT_ADMIN_EMAIL="$2"
      shift 2
      ;;
    --admin-password)
      DEFAULT_ADMIN_PASSWORD="$2"
      shift 2
      ;;
    --admin-name)
      DEFAULT_ADMIN_NAME="$2"
      shift 2
      ;;
    --no-admin)
      CREATE_ADMIN=0
      shift
      ;;
    --help)
      echo "Usage: $0 [options]"
      echo "Options:"
      echo "  --port PORT             Base port number (default: 8080)"
      echo "  --include NAME          Include only specified worktree(s)"
      echo "  --exclude NAME          Exclude specified worktree(s)"
      echo "  --skip-deps             Skip dependency installation"
      echo "  --admin-email EMAIL     Admin email address (default: admin@grill-stats.lab.apj.dev)"
      echo "  --admin-password PASS   Admin password (default: admin1234)"
      echo "  --admin-name NAME       Admin name (default: Administrator)"
      echo "  --no-admin              Don't create admin user"
      echo "  --help                  Show this help message"
      exit 0
      ;;
    *)
      echo -e "${RED}Unknown option: $1${NC}"
      echo "Use --help for usage information"
      exit 1
      ;;
  esac
done

# Create base directory for worktrees if it doesn't exist
WORKTREE_BASE_DIR="./trees"
mkdir -p $WORKTREE_BASE_DIR

# Check if in git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
  echo -e "${RED}Error: Not in a git repository${NC}"
  exit 1
fi

# Dynamic worktree detection
declare -A SERVICES
PORT=$BASE_PORT

# If no worktrees specified to include, scan directory for all worktrees
if [ ${#SPECIFIED_WORKTREES[@]} -eq 0 ]; then
  # Check if trees directory exists and has subdirectories
  if [ -d "$WORKTREE_BASE_DIR" ]; then
    # Get all subdirectories of the trees directory
    for dir in "$WORKTREE_BASE_DIR"/*; do
      if [ -d "$dir" ]; then
        # Extract the service name from the directory path
        service_name=$(basename "$dir")

        # Skip if this service is in the exclude list
        skip=false
        for excluded in "${EXCLUDE_WORKTREES[@]}"; do
          if [[ "$service_name" == "$excluded" || "$service_name" == "$excluded"* ]]; then
            skip=true
            break
          fi
        done

        if [ "$skip" = true ]; then
          echo -e "${YELLOW}Skipping excluded worktree: $service_name${NC}"
          continue
        fi

        # Assign a port to this service
        SERVICES["$service_name"]=$PORT
        PORT=$((PORT + 1))
        echo -e "${BLUE}Found worktree: $service_name, assigned port: ${SERVICES[$service_name]}${NC}"
      fi
    done
  fi
else
  # Use only specified worktrees
  for service_name in "${SPECIFIED_WORKTREES[@]}"; do
    if [ -d "$WORKTREE_BASE_DIR/$service_name" ]; then
      SERVICES["$service_name"]=$PORT
      PORT=$((PORT + 1))
      echo -e "${BLUE}Using specified worktree: $service_name, assigned port: ${SERVICES[$service_name]}${NC}"
    else
      echo -e "${YELLOW}Specified worktree not found: $service_name${NC}"
    fi
  done
fi

# If no worktrees found or specified, use default services
if [ ${#SERVICES[@]} -eq 0 ]; then
  echo -e "${BLUE}No existing worktrees found, using default services${NC}"

  # Default service names and their ports
  SERVICES=(
    ["auth-service"]=$((BASE_PORT + 1))
    ["device-service"]=$BASE_PORT
    ["temperature-service"]=$((BASE_PORT + 2))
    ["historical-data-service"]=$((BASE_PORT + 3))
    ["encryption-service"]=$((BASE_PORT + 4))
    ["web-ui"]="80"
  )
fi

# Create worktrees and start services
PIDS=()
SERVICE_NAMES=()

for service in "${!SERVICES[@]}"; do
  # Create worktree directory if it doesn't exist
  WORKTREE_DIR="$WORKTREE_BASE_DIR/$service"

  # Check if worktree already exists
  if [ ! -d "$WORKTREE_DIR" ]; then
    echo -e "${BLUE}Creating worktree for $service...${NC}"

    # Try to use service name as branch name first, fallback to main
    if git show-ref --verify --quiet refs/heads/"$service"; then
      git worktree add "$WORKTREE_DIR" "$service"
    else
      echo -e "${YELLOW}Branch '$service' not found, using main branch${NC}"
      git worktree add "$WORKTREE_DIR" main
    fi

    if [ $? -ne 0 ]; then
      echo -e "${RED}Failed to create worktree for $service${NC}"
      continue
    fi
  fi

  # Start service
  PORT=${SERVICES[$service]}
  echo -e "${BLUE}Starting $service on port $PORT...${NC}"

  # Determine how to start service based on service type
  cd "$WORKTREE_DIR"

  # Auto-detect service type based on files present
  if [ -f "package.json" ]; then
    # JavaScript/TypeScript service
    echo -e "${BLUE}Detected JS/TS service${NC}"

    # Install dependencies if node_modules doesn't exist and not skipping deps
    if [ ! -d "node_modules" ] && [ $SKIP_DEPS -eq 0 ]; then
      echo -e "${YELLOW}Installing npm dependencies...${NC}"
      npm install || yarn install
    fi

    # Run in background and save PID
    (npm run dev -- --port $PORT || yarn dev --port $PORT) &
    PID=$!
    PIDS+=($PID)
    SERVICE_NAMES+=($service)
    echo -e "${GREEN}✓ $service started (PID: $PID)${NC}"

  elif [ -f "app.py" ] || [ -f "main.py" ]; then
    # Python service
    if [ -f "app.py" ]; then
      PYTHON_MAIN="app.py"
      echo -e "${BLUE}Detected Python service (app.py)${NC}"
    else
      PYTHON_MAIN="main.py"
      echo -e "${BLUE}Detected Python service (main.py)${NC}"
    fi

    # Install dependencies if requirements.txt exists and not skipping deps
    if [ -f "requirements.txt" ] && [ $SKIP_DEPS -eq 0 ]; then
      echo -e "${YELLOW}Installing Python dependencies...${NC}"

      # Create virtual environment if it doesn't exist
      if [ ! -d ".venv" ]; then
        echo -e "${BLUE}Creating virtual environment...${NC}"
        python3 -m venv .venv
      fi

      # Activate virtual environment and install dependencies
      source .venv/bin/activate
      pip install -r requirements.txt

      # Set environment variables for the service
      export PORT=$PORT
      export ADMIN_EMAIL=$DEFAULT_ADMIN_EMAIL
      export ADMIN_PASSWORD=$DEFAULT_ADMIN_PASSWORD
      export ADMIN_NAME=$DEFAULT_ADMIN_NAME
      export CREATE_ADMIN=$CREATE_ADMIN

      # Run in background and save PID
      python3 $PYTHON_MAIN &
      PID=$!
      PIDS+=($PID)
      SERVICE_NAMES+=($service)
      echo -e "${GREEN}✓ $service started (PID: $PID)${NC}"

      # Deactivate virtual environment
      deactivate
    else
      # Install common dependencies if not skipping deps
      if [ $SKIP_DEPS -eq 0 ]; then
        echo -e "${YELLOW}No requirements.txt found. Installing common dependencies...${NC}"

        # Create virtual environment if it doesn't exist
        if [ ! -d ".venv" ]; then
          echo -e "${BLUE}Creating virtual environment...${NC}"
          python3 -m venv .venv
        fi

        # Activate virtual environment and install common dependencies
        source .venv/bin/activate
        pip install flask apscheduler requests python-dotenv pydantic
      else
        # Create virtual environment if it doesn't exist
        if [ ! -d ".venv" ]; then
          echo -e "${BLUE}Creating virtual environment...${NC}"
          python3 -m venv .venv
        fi

        # Just activate the virtual environment without installing deps
        source .venv/bin/activate
      fi

      # Set environment variables for the service
      export PORT=$PORT
      export ADMIN_EMAIL=$DEFAULT_ADMIN_EMAIL
      export ADMIN_PASSWORD=$DEFAULT_ADMIN_PASSWORD
      export ADMIN_NAME=$DEFAULT_ADMIN_NAME
      export CREATE_ADMIN=$CREATE_ADMIN

      # Run in background and save PID
      python3 $PYTHON_MAIN &
      PID=$!
      PIDS+=($PID)
      SERVICE_NAMES+=($service)
      echo -e "${GREEN}✓ $service started (PID: $PID)${NC}"

      # Deactivate virtual environment
      deactivate
    fi

  elif [ -f "go.mod" ]; then
    # Go service
    echo -e "${BLUE}Detected Go service${NC}"

    # Install Go dependencies if not skipping deps
    if [ $SKIP_DEPS -eq 0 ]; then
      echo -e "${YELLOW}Installing Go dependencies...${NC}"
      go mod download
    fi

    # Set environment variables for the service
    export PORT=$PORT

    # Run in background and save PID
    go run . &
    PID=$!
    PIDS+=($PID)
    SERVICE_NAMES+=($service)
    echo -e "${GREEN}✓ $service started (PID: $PID)${NC}"

  elif [ -f "Cargo.toml" ]; then
    # Rust service
    echo -e "${BLUE}Detected Rust service${NC}"

    # Check if cargo is available
    if command -v cargo &>/dev/null; then
      # Build dependencies if not skipping deps
      if [ $SKIP_DEPS -eq 0 ]; then
        echo -e "${YELLOW}Building Rust dependencies...${NC}"
        cargo build
      fi

      # Set environment variables for the service
      export PORT=$PORT

      # Run in background and save PID
      cargo run &
      PID=$!
      PIDS+=($PID)
      SERVICE_NAMES+=($service)
      echo -e "${GREEN}✓ $service started (PID: $PID)${NC}"
    else
      echo -e "${RED}Cargo not found. Please install Rust to run this service.${NC}"
    fi

  else
    echo -e "${RED}Could not determine service type for $service${NC}"
    echo -e "${YELLOW}Supported entry points: app.py, main.py, package.json, go.mod, Cargo.toml${NC}"
  fi

  # Return to base directory
  cd - > /dev/null
done

# Print summary
if [ ${#PIDS[@]} -gt 0 ]; then
  echo -e "\n${YELLOW}Services started: ${#PIDS[@]}${NC}"
  echo -e "${YELLOW}Access them at:${NC}"

  # Print access URLs
  for i in "${!SERVICE_NAMES[@]}"; do
    service=${SERVICE_NAMES[$i]}
    PORT=${SERVICES[$service]}
    echo -e "  ${GREEN}http://localhost:$PORT${NC} - $service"
  done

  echo -e "\n${YELLOW}Press Ctrl+C to stop all services${NC}"

  # Handle Ctrl+C to stop all services
  trap 'echo -e "\n${YELLOW}Stopping all services...${NC}"; for pid in "${PIDS[@]}"; do kill $pid 2>/dev/null; done; echo -e "${GREEN}All services stopped${NC}"; exit 0' INT

  # Wait for any process to exit
  wait ${PIDS[0]}
else
  echo -e "${RED}No services were started${NC}"
  exit 1
fi
