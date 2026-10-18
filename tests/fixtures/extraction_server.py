"""Dummy MCP server for consent tests. Never invokes an analyzer."""
from types import SimpleNamespace
from mcp.server import MCPServer
from volatility_workbench.guarded_scoped import ExtractionGuard
server=MCPServer('synthetic-extraction')
@server.tool()
def run_plugin(image:str,plugin:str,arguments:list[str]|None=None)->dict:
    return {'synthetic':True,'plugin':plugin,'arguments':arguments}
@server.tool()
def query_output()->dict:return {'saved':True}
backend=SimpleNamespace(validate_arguments=lambda p,a:a,list_plugins=lambda p:{'plugins':[
    {'name':p,'description':'Lists processes' if p=='windows.pslist.PsList' else 'Dumps files',
     'options':[{'flag':'--dump'}] if p=='windows.pslist.PsList' else []}]})
server.middleware.append(ExtractionGuard(backend,'/synthetic/outputs'))
server.run(transport='stdio')
