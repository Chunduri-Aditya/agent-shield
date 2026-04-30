"""
Agent Shield — tools/ module
MCP tool poisoning and confused deputy attacks. L2 adversary level.
"""

from .attacks import TOOL_ATTACKS, ToolAttack

__all__ = ["TOOL_ATTACKS", "ToolAttack"]
