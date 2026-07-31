"""CenkorMES AI Agent Tool Registry (fixed - auto registers builtin tools).

Usage:
    from app.services.ai.agent.tools_registry import registry
    tools = registry.get_tools()  # Returns list for OpenAI function calling
    result = registry.execute("query_orders", {"status": "pending"}, {"db": session, "tenant_id": 1})
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Dict] = {}
        self._handlers: Dict[str, Callable] = {}
        self._initialized = False

    def _ensure_init(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        try:
            import importlib
            importlib.import_module("app.services.ai.agent.builtin_tools")
            logger.info(f"Auto-registered {len(self._tools)} builtin agent tools")
        except Exception as e:
            logger.warning(f"Failed to auto-register builtin tools: {e}")

    def register(self, code: str, description: str, parameters: dict, handler: Callable) -> None:
        self._tools[code] = {
            "type": "function",
            "function": {
                "name": code,
                "description": description,
                "parameters": parameters,
            },
        }
        self._handlers[code] = handler

    def get_tools(self) -> List[Dict]:
        self._ensure_init()
        return list(self._tools.values())

    def get_tool_names(self) -> List[str]:
        self._ensure_init()
        return list(self._tools.keys())

    def execute(self, code: str, arguments: Dict[str, Any], context: Dict) -> str:
        self._ensure_init()
        if code not in self._handlers:
            return f"Error: tool '{code}' not found (available: {', '.join(self._handlers.keys())})"
        try:
            return str(self._handlers[code](arguments, context))
        except Exception as e:
            logger.error(f"Tool '{code}' execution failed: {e}")
            return f"Error executing '{code}': {str(e)[:200]}"


registry = ToolRegistry()
