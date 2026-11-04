"""Local MCP client: discovery without downloads, opt-in real manual search."""
import argparse
import os
from datetime import timedelta
import asyncio
import json
from pathlib import Path
import sys


async def query_server(query=None, machine_type='fan'):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    root = Path(__file__).resolve().parents[1]
    keys = (
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC",
        "TEMP", "TMP", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
        "HOME", "HOMEDRIVE", "HOMEPATH", "VIRTUAL_ENV",
        "MACHINEEAR_RESOURCE_ROOT"
    )
    env = {
        key: value for key, value in os.environ.items()
        if key.upper() in keys
    }
    print("1. Démarrage du serveur MCP...", file=sys.stderr, flush=True)
    params = StdioServerParameters(env=env, command=sys.executable, args=[str(root / 'server.py')], cwd=str(root))
    async with stdio_client(params) as (read, write):
        async with ClientSession(
            read, write,
            read_timeout_seconds=timedelta(seconds=90)
        ) as session:
            await session.initialize()
            print("2. Connexion MCP établie.", file=sys.stderr, flush=True)
            listing = await session.list_tools()
            if query is None:
                return {'tools': [tool.name for tool in listing.tools]}
            print("3. Appel de la recherche...", file=sys.stderr, flush=True)
            result = await session.call_tool('search_manuals', {
                'query': query, 'machine_type': machine_type, 'language': 'auto', 'top_k': 3})
            return result.model_dump(mode='json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query')
    parser.add_argument('--machine-type', choices=['fan', 'pump'], default='fan')
    args = parser.parse_args()
    print(json.dumps(asyncio.run(query_server(args.query, args.machine_type)), indent=2))
