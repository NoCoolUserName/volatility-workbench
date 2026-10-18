"""Synthetic MCP transport only; never starts an analyzer or opens an image."""
import os
from mcp.server import MCPServer
from volatility_workbench.guarded_scoped import install_volshell_bridge

server = MCPServer('synthetic-volshell-bridge')

@server.tool()
async def run_plugin(image: str, plugin: str, arguments: list[str]) -> dict:
    return {'synthetic':True, 'image':image, 'plugin':plugin, 'arguments':arguments}

install_volshell_bridge(server, os.environ.get('WORKBENCH_VOLSHELL_BRIDGE'))
server.run(transport='stdio')
