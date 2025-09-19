from typing import Dict, List, Optional
import logging
import aiohttp
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

# MCPツール→システム種別マッピング辞書 (グローバル設定)
MCP_TOOL_SYSTEM_MAP = {
    # ProductMaster MCP ツール
    'get_product_details': 'productmaster',
    'search_products_by_name_fuzzy': 'productmaster',
    
    # CRM MCP ツール
    'search_customers_by_bond_maturity': 'crm',
    'get_customer_holdings': 'crm',
    'predict_cash_inflow_from_sales_notes': 'crm',
    'get_customers_by_product': 'crm',
}

# システム種別→アイコンマッピング辞書 (グローバル設定)
MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      # 📦 商品管理
    'crm': 'fa-users',              # 👥 顧客管理
    'default': 'fa-tool'            # 🔧 デフォルト
}

class MCPManager:
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.available_tools: Dict[str, Dict[str, any]] = {}
        self.mcp_management_url = "http://localhost:8008"
        
        # 既存MCP設定（後方互換性のため保持）
        self.available_mcps = {
            'productmaster': {
                'name': 'ProductMaster MCP',
                'description': '商品情報検索・管理',
                'url': 'http://localhost:8003',
                'enabled': True
            },
            'crm': {
                'name': 'CRM MCP', 
                'description': '顧客管理・債券満期検索',
                'url': 'http://localhost:8004',
                'enabled': True
            }
        }

    async def get_tools_from_management(self) -> Dict[str, Dict[str, any]]:
        """MCP-Management APIからツール情報を取得"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_management_url}/api/tools") as response:
                    if response.status == 200:
                        tools_data = await response.json()
                        tools_dict = {}
                        for tool in tools_data:
                            tools_dict[tool['tool_key']] = {
                                'name': tool['tool_name'],
                                'description': tool['description'],
                                'remarks': tool.get('remarks', '')
                            }
                        logger.info(f"MCP-Management から {len(tools_dict)} 個のツール情報を取得")
                        return tools_dict
                    else:
                        logger.error(f"MCP-Management API エラー: {response.status}")
                        return {}
        except Exception as e:
            logger.error(f"MCP-Management API 接続エラー: {e}")
            return {}

    async def initialize(self):
        """全MCPクライアントを初期化"""
        for mcp_id, config in self.available_mcps.items():
            if config['enabled']:
                try:
                    self.clients[mcp_id] = MCPClient(config['url'])
                    logger.info(f"MCP初期化成功: {mcp_id} ({config['url']})")
                except Exception as e:
                    logger.error(f"MCP初期化失敗: {mcp_id} - {e}")

    async def discover_available_tools(self):
        """MCP-Management + 各MCPサーバーでツール利用可能性確認"""
        # 1. MCP-Management からツール情報取得
        management_tools = await self.get_tools_from_management()
        
        # 2. 各MCPサーバーで利用可能性確認
        self.available_tools.clear()
        
        for tool_key, tool_info in management_tools.items():
            # ツールキーからMCPサーバー判定
            mcp_server = self._get_mcp_server_by_tool(tool_key)
            if mcp_server and mcp_server in self.available_mcps:
                # MCPサーバーでツール利用可能性確認
                if await self._check_tool_available(mcp_server, tool_key):
                    self.available_tools[tool_key] = {
                        'name': tool_info['name'],
                        'description': tool_info['description'],
                        'mcp_server': mcp_server,
                        'url': self.available_mcps[mcp_server]['url']
                    }
                    logger.info(f"ツール利用可能: {tool_key} ({mcp_server})")
                else:
                    logger.warning(f"ツール利用不可: {tool_key} ({mcp_server})")
        
        logger.info(f"利用可能ツール: {len(self.available_tools)} 個")

    def _get_mcp_server_by_tool(self, tool_key: str) -> Optional[str]:
        """ツールキーからMCPサーバーを判定"""
        if tool_key in ['search_products_by_name_fuzzy', 'get_product_details']:
            return 'productmaster'
        elif tool_key in ['search_customers_by_bond_maturity', 'get_customer_holdings', 'get_customers_by_product']:
            return 'crm'
        return None

    async def _check_tool_available(self, mcp_server: str, tool_key: str) -> bool:
        """指定MCPサーバーでツールが利用可能かチェック"""
        try:
            if mcp_server not in self.clients:
                self.clients[mcp_server] = MCPClient(self.available_mcps[mcp_server]['url'])
            
            # MCPサーバーのツール一覧取得
            tools_list = await self.clients[mcp_server].list_tools()
            return any(tool.get('name') == tool_key for tool in tools_list.get('tools', []))
        except Exception as e:
            logger.error(f"ツール確認エラー {tool_key} @ {mcp_server}: {e}")
            return False

    def get_strategy_prompt_tools(self) -> str:
        """戦略立案用のツール説明文字列生成"""
        tool_descriptions = []
        for tool_key, tool_info in self.available_tools.items():
            desc = f"{tool_key}: {tool_info['name']} - {tool_info['description']}"
            tool_descriptions.append(desc)
        
        return "\n".join(tool_descriptions)

    def get_enabled_tools(self) -> Dict[str, str]:
        """有効なツール一覧を取得（既存互換性のため）"""
        return {
            tool_key: tool_info['name'] 
            for tool_key, tool_info in self.available_tools.items()
        }

    async def process_with_mcp(self, message: str, mcp_id: str = 'productmaster'):
        """指定MCPでメッセージ処理"""
        import time
        start_time = time.time()
        
        try:
            if mcp_id not in self.clients:
                self.clients[mcp_id] = MCPClient(self.available_mcps[mcp_id]['url'])
            
            result = await self.clients[mcp_id].call_tool('search_products_by_name_fuzzy', {'text_input': message})
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'success',
                'result': result,
                'mcp_server': mcp_id,
                'processing_time_ms': processing_time,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            logger.error(f"MCP処理エラー ({mcp_id}): {e}")
            return {
                'status': 'error',
                'error': str(e),
                'mcp_server': mcp_id,
                'processing_time_ms': (time.time() - start_time) * 1000,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
