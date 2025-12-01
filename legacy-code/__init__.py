from pathlib import Path
import sys

# Add the current directory to Python path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Add the parent directory to Python path (enables import of 'base')
parent_dir = current_dir.parent.parent  # This goes up two levels to scrapers/
sys.path.append(str(parent_dir))
