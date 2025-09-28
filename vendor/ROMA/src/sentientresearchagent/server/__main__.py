"""
Main entry point for running the server as a module.

Usage:
    python -m sentientresearchagent.server
"""

from .main import create_server

if __name__ == '__main__':
    server = create_server()
    server.run() 