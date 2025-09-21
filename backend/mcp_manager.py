import asyncio
import logging
from typing import Dict, Optional, List, Any
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

class MCPManager:
    """MCP (Model Context Protocol) ツール管理クラス
    
    ツール状態の定義:
    - Available: MCPサーバーから取得可能なツール
    - Enabled: 実際に使用可能なツール（Availableかつ有効化済み）
    """
    
    def __init__(self):
        self.available_mcps = {
            'productmaster': {
                'name': 'ProductMaster MCP',
                'description': '商品情報検索システム',
                'url': 'http://localhost:8003',
                'enabled': True
            },
            'crm': {
                'name': 'CRM MCP',
                'description': '顧客管理システム',
                'url': 'http://localhost:8004',
                'enabled': True
            }
        }
        self.clients: Dict[str, MCPClient] = {}
        self.available_tools: Dict[str, Dict[str, Any]] = {}
    
    async def initialize(self):
        """MCPマネージャー初期化"""
        logger.info("MCP Manager 初期化開始")
        await self.discover_available_tools()
        logger.info("MCP Manager 初期化完了")
    
    async def discover_available_tools(self):
        """MCPサーバーから利用可能ツールを取得"""
        logger.info("利用可能ツールを探索中...")
        
        self.available_tools.clear()
        
        for mcp_id, mcp_config in self.available_mcps.items():
            if not mcp_config['enabled']:
                continue
                
            try:
                if mcp_id not in self.clients:
                    self.clients[mcp_id] = MCPClient(mcp_config['url'])
                
                tools_list = await self.clients[mcp_id].list_tools()
                for tool in tools_list:  # List を直接イテレート
                    tool_key = tool.get('name')
                    if tool_key:
                        self.available_tools[tool_key] = {
                            'name': tool.get('description', tool_key),
                            'mcp_server': mcp_id,
                            'enabled': True  # デフォルトで有効
                        }
            except Exception as e:
                logger.error(f"MCP {mcp_id} ツール取得エラー: {e}")
        
        logger.info(f"利用可能ツール: {len(self.available_tools)} 個")
    
    def is_tool_available(self, tool_name: str) -> bool:
        """ツールがMCPサーバーから取得可能か確認"""
        return tool_name in self.available_tools
    
    def is_tool_enabled(self, tool_name: str) -> bool:
        """ツールが有効化されているか確認（AvailableかつEnabled）"""
        if not self.is_tool_available(tool_name):
            return False
        return self.available_tools[tool_name].get('enabled', False)
    
    def toggle_tool_enabled(self, tool_name: str) -> bool:
        """ツールの有効/無効を切り替え"""
        if not self.is_tool_available(tool_name):
            return False
        
        current_enabled = self.available_tools[tool_name].get('enabled', False)
        self.available_tools[tool_name]['enabled'] = not current_enabled
        return not current_enabled
    
    def get_strategy_prompt_tools(self) -> str:
        """戦略エンジン用ツール説明を生成"""
        enabled_tools = self.get_enabled_tools_dict()
        if not enabled_tools:
            return "利用可能なツールはありません。"
        
        tools_desc = "利用可能なツール:\n"
        for tool_key, tool_info in enabled_tools.items():
            tools_desc += f"- {tool_key}: {tool_info['name']}\n"
        return tools_desc
    
    def get_enabled_tools_dict(self) -> Dict[str, Dict[str, Any]]:
        """有効なツールの詳細情報を取得"""
        return {
            tool_key: tool_info 
            for tool_key, tool_info in self.available_tools.items()
            if tool_info.get('enabled', False)
        }
    
    def get_enabled_tools(self) -> Dict[str, str]:
        """有効なツール一覧を取得（既存互換性のため）"""
        return {
            tool_key: tool_info['name'] 
            for tool_key, tool_info in self.available_tools.items()
            if tool_info.get('enabled', False)
        }
