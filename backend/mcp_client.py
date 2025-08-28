import asyncio
import json
import httpx
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class MCPClient:
    def __init__(self, server_url: str = "http://localhost:8003"):
        self.server_url = server_url
        self.mcp_endpoint = f"{server_url}/mcp"
        self.health_endpoint = f"{server_url}/health"
        self.request_id = 1
        self.initialized = False
        self.available_tools = []
    
    def _get_next_id(self) -> int:
        current_id = self.request_id
        self.request_id += 1
        return current_id
    
    async def _send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method,
            "params": params or {}
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(self.mcp_endpoint, json=request)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                logger.error(f"MCP request failed: {e}")
                return {"error": str(e)}
    
    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(self.health_endpoint)
                return response.status_code == 200
        except:
            return False
    
    async def initialize(self) -> bool:
        try:
            params = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "aichat-mcp-client", "version": "1.0.0"}
            }
            result = await self._send_request("initialize", params)
            
            if "result" in result:
                self.initialized = True
                logger.info("MCP initialized successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"MCP initialize failed: {e}")
            return False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        try:
            result = await self._send_request("tools/list")
            if "result" in result and "tools" in result["result"]:
                self.available_tools = result["result"]["tools"]
                return self.available_tools
            return []
        except Exception as e:
            logger.error(f"Tools list failed: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        try:
            params = {"name": tool_name, "arguments": arguments}
            result = await self._send_request("tools/call", params)
            
            if "result" in result:
                return result["result"]
            else:
                return {"error": "Tool execution failed"}
        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return {"error": str(e)}
