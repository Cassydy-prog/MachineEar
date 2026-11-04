"""Local read-only MCP server for MachineEar manuals."""
import asyncio
import faulthandler
from pathlib import Path
import sys
import traceback
from typing import Literal

from mcp.server.fastmcp import FastMCP
from machineear.agent_tools.executor import ToolExecutor


def create_server(executor=None, diagnostic=None):
    executor = executor or ToolExecutor()
    diagnostic = diagnostic or sys.stderr
    server = FastMCP("MachineEar manuals")

    @server.tool()
    async def search_manuals(
        query: str,
        machine_type: Literal["fan", "pump"],
        language: Literal["en", "fr", "auto", "all"] = "auto",
        top_k: int = 3
    ) -> dict:
        """Read verified manual passages with physical PDF citations."""
        print("TOOL_ENTER: search_manuals", file=diagnostic, flush=True)
        faulthandler.dump_traceback_later(30, file=diagnostic)
        try:
            result = await asyncio.to_thread(
                executor.execute,
                "search_manuals",
                {
                    "query": query,
                    "machine_type": machine_type,
                    "language": language,
                    "top_k": top_k
                }
            )
            print("TOOL_EXIT: success", file=diagnostic, flush=True)
            return result
        except Exception:
            traceback.print_exc(file=diagnostic)
            diagnostic.flush()
            raise
        finally:
            faulthandler.cancel_dump_traceback_later()

    return server


if __name__ == "__main__":
    log_path = Path(__file__).resolve().with_name("mcp_debug.log")
    with log_path.open("w", encoding="utf-8", buffering=1) as log:
        print("SERVER_START", file=log, flush=True)
        faulthandler.enable(file=log)
        faulthandler.dump_traceback_later(30, file=log)
        try:
            print("NATIVE_RUNTIME_START", file=log, flush=True)
            from machineear.runtime import prepare_native_runtime
            prepare_native_runtime()

            print("NUMPY_IMPORT_START", file=log, flush=True)
            import numpy
            print("NUMPY_IMPORT_OK", file=log, flush=True)

            create_server(diagnostic=log).run(transport="stdio")
        finally:
            faulthandler.cancel_dump_traceback_later()
