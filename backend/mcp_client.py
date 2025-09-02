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
        import time
        start_time = time.time()
        
        logger.info(f"[DEBUG] call_tool called with: {tool_name}, {arguments}")
        
        try:
            params = {"name": tool_name, "arguments": arguments}
            result = await self._send_request("tools/call", params)
            processing_time = round((time.time() - start_time) * 1000, 2)
            
            logger.info(f"[DEBUG] MCP server response: {result}")
            
            if "result" in result:
                # debug_responseの確認
                debug_response = result.get("debug_response")
                logger.info(f"[DEBUG] debug_response from server: {debug_response}")
                logger.info(f"[DEBUG] debug_response type: {type(debug_response)}")
                
                # debug_infoを統合形式で生成
                debug_info = {
                    "request": {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "server_url": self.server_url,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "response": {
                        "processing_time_ms": processing_time,
                        "request_id": result.get("id"),
                        "status": "success",
                        "tool_debug": debug_response
                    }
                }
                
                logger.info(f"[DEBUG] Generated debug_info: {debug_info}")
                logger.info(f"[DEBUG] tool_debug in debug_info: {debug_info['response']['tool_debug']}")
                
                response = {
                    "result": result["result"],
                    "debug_info": debug_info
                }
                logger.info(f"[DEBUG] Final response: {response}")
                return response
            else:
                return {
                    "error": "Tool execution failed",
                    "debug_info": {
                        "request": {
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "server_url": self.server_url,
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                        },
                        "response": {
                            "processing_time_ms": processing_time,
                            "status": "error",
                            "error": "No result in response"
                        }
                    }
                }
        except Exception as e:
            processing_time = round((time.time() - start_time) * 1000, 2)
            logger.error(f"Tool call failed: {e}")
            return {
                "error": str(e),
                "debug_info": {
                    "request": {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "server_url": self.server_url,
                        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "response": {
                        "processing_time_ms": processing_time,
                        "status": "exception",
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                }
            }
