"""Agent tools Jitera adds to every scan agent.

Write a tool the way upstream does (see ``strix/tools/thinking/tool.py``):

    # strix/jitera/tools/ticket.py
    from agents import function_tool

    @function_tool(timeout=30)
    async def create_ticket(title: str, body: str) -> str:
        \"\"\"File a confirmed finding in the Jitera tracker.\"\"\"
        ...

Then import it in ``get_tools`` below. ``strix.jitera.bootstrap`` registers the list
with upstream's ``register_agent_tools`` before a scan starts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from agents.tool import Tool


def get_tools() -> list[Tool]:
    """Return the tools to register. Import tool modules here, not at the top."""
    from strix.jitera.tools.component_scan import detect_vulnerable_components
    from strix.jitera.tools.exposure_scan import scan_static_exposure
    from strix.jitera.tools.payload_oracle import check_payload_fired

    return [detect_vulnerable_components, scan_static_exposure, check_payload_fired]
