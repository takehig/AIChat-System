from mcp_tool_manager import MCPToolManager
import httpx
import logging
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

# タイムアウト設定
TIMEOUT_CONFIG = {
    "mcp_request_timeout": 30.0
}

class TimeoutException(Exception):
    pass

class MCPClient:
    """MCP Client - MCPToolManager 統合・ツール名のみ受け取り設計"""
    
    def __init__(self, tool_manager: MCPToolManager):
        self.tool_manager = tool_manager  # MCPToolManager 注入
        self.request_id = 1
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """ツール実行 - ツール名のみ受け取り・内部で完全管理"""
        start_time = time.time()
        
        print(f"[MCP_CLIENT] === CALL_TOOL START ===")
        print(f"[MCP_CLIENT] Tool: {tool_name}")
        print(f"[MCP_CLIENT] Arguments: {arguments}")
        
        # ツール情報取得
        if tool_name not in self.tool_manager.registered_tools:
            return {"error": f"Tool '{tool_name}' not found"}
        
        tool = self.tool_manager.registered_tools[tool_name]
        
        # 状態確認
        if not tool.enabled:
            return {"error": f"Tool '{tool_name}' is disabled"}
        
        if not tool.available:
            return {"error": f"Tool '{tool_name}' is not available"}
        
        # ルーティング決定
        if tool.mcp_server_name == "CRM MCP":
            server_url = "http://localhost:8004/mcp"
        elif tool.mcp_server_name == "ProductMaster MCP":
            server_url = "http://localhost:8003/mcp"
        else:
            return {"error": f"Unknown MCP server: {tool.mcp_server_name}"}
        
        print(f"[MCP_CLIENT] Server URL: {server_url}")
        
        # call_tool 実行情報初期化
        call_tool_info = {
            "request": {
                "tool_name": tool_name,
                "arguments": arguments,
                "server_url": server_url,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "response": {
                "processing_time_ms": None,
                "request_id": None,
                "status": None,
                "tool_debug": None
            }
        }
        
        try:
            # JSON-RPC リクエスト作成
            request_id = int(time.time() * 1000000)  # マイクロ秒精度
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            print(f"[MCP_CLIENT] Request payload: {payload}")
            
            # HTTP通信実行
            async with httpx.AsyncClient(timeout=TIMEOUT_CONFIG["mcp_request_timeout"]) as client:
                response = await client.post(server_url, json=payload)
                processing_time = (time.time() - start_time) * 1000
                
                call_tool_info["response"]["processing_time_ms"] = processing_time
                call_tool_info["response"]["request_id"] = request_id
                call_tool_info["response"]["status"] = response.status_code
                
                if response.status_code == 200:
                    mcp_dict = response.json()
                    
                    # call_tool 実行情報設定
                    call_tool_info["response"]["tool_debug"] = mcp_dict.get("debug_response")
                    print(f"[MCP_CLIENT] debug_response from server: {call_tool_info['response']['tool_debug']}")
                    
                    # 最終レスポンス作成
                    final_response = {
                        "jsonrpc": mcp_dict.get("jsonrpc"),
                        "id": mcp_dict.get("id"),
                        "result": mcp_dict.get("result"),
                        "error": mcp_dict.get("error"),
                        "debug_info": call_tool_info  # call_tool 実行情報
                    }
                    
                    print(f"[MCP_CLIENT] Final response: {final_response}")
                    print(f"[MCP_CLIENT] === CALL_TOOL SUCCESS ===")
                    return final_response
                else:
                    call_tool_info["response"]["tool_debug"] = {"error": f"HTTP {response.status_code}", "response_text": response.text}
                    return {
                        "error": f"MCP server error: {response.status_code} - {response.text}",
                        "debug_info": call_tool_info
                    }
                    
        except Exception as e:
            call_tool_info["response"]["tool_debug"] = {"error": str(e), "error_type": type(e).__name__}
            
            print(f"[MCP_CLIENT] === CALL_TOOL ERROR ===")
            print(f"[MCP_CLIENT] Exception occurred: {e}")
            print(f"[MCP_CLIENT] Exception type: {type(e)}")
            
            return {
                "error": f"MCP execution failed: {str(e)}",
                "debug_info": call_tool_info
            }
