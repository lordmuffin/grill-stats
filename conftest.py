import os
import sys

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Add services directory to Python path
services_dir = os.path.join(project_root, "services")
sys.path.insert(0, services_dir)
