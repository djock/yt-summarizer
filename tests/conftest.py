import os
import sys

# Ensure the project root is on sys.path so packages (core, pipeline, utils) are importable
# without requiring `pip install -e .`
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
