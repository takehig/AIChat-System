from typing import Dict, List, Optional
import logging
from mcp_client import MCPClient

logger = logging.getLogger(__name__)

# MCPツール→システム種別マッピング辞書 (グローバル設定)
MCP_TOOL_SYSTEM_MAP = {
    # ProductMaster MCP ツール (実際のツール名)
    'get_product_details': 'productmaster',
    
    # CRM MCP ツール (実際のツール名)
    'search_customers_by_bond_maturity': 'crm',
    'get_customer_holdings': 'crm',
    
    # 将来追加用 (例)
    # 'get_market_data': 'market_data',
    # 'get_news': 'news_system',
}

# システム種別→アイコンマッピング辞書 (グローバル設定)
MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      # 📦 商品管理
    'crm': 'fa-users',              # 👥 顧客管理
    'market_data': 'fa-chart-line', # 📈 市場データ (将来用)
    'news_system': 'fa-newspaper',  # 📰 ニュース (将来用)
    'default': 'fa-tool'            # 🔧 デフォルト
}

class MCPManager:
    def __init__(self):
        self.mcp_clients: Dict[str, MCPClient] = {}
        self.mcp_status: Dict[str, bool] = {"productmaster": False, "crm": False}
        self.available_mcps: Dict[str, dict] = {
        'crm': {
            'name': 'CRM',
            'description': '顧客管理システムとの連携機能',
            'url': 'http://localhost:8004',
            'enabled': False
        },
            'productmaster': {
                'name': 'ProductMaster',
                'description': '商品情報検索MCP',
                'url': 'http://localhost:8003',
                'enabled': False
            }
            # 将来の拡張用
            # 'market_data': {
            #     'name': 'MarketData',
            #     'description': '市場データ取得MCP',
            #     'url': 'http://localhost:8004',
            #     'enabled': False
            # }
        }
    async def initialize(self):
        """全MCPクライアントを初期化"""
        for mcp_id, config in self.available_mcps.items():
            try:
                client = MCPClient(config['url'])
                if await client.health_check():
                    await client.initialize()
                    self.mcp_clients[mcp_id] = client
                    self.mcp_status[mcp_id] = config['enabled']
                    logger.info(f"✅ {config['name']} MCP initialized")
                else:
                    logger.warning(f"⚠️ {config['name']} MCP health check failed")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {config['name']} MCP: {e}")
    def get_tool_system_type(self, tool_name: str) -> str:
        """ツール名からシステム種別を取得"""
        return MCP_TOOL_SYSTEM_MAP.get(tool_name, 'default')
    
    def get_tool_icon(self, tool_name: str) -> str:
        """ツール名からアイコンクラスを取得"""
        system_type = self.get_tool_system_type(tool_name)
        return MCP_SYSTEM_ICONS.get(system_type, MCP_SYSTEM_ICONS['default'])
    
    def get_mcp_status(self, mcp_id: str = 'productmaster') -> dict:
        """MCP状態取得"""
        if mcp_id not in self.available_mcps:
            return {'available': False, 'enabled': False}
        return {
            'available': mcp_id in self.mcp_clients,
            'enabled': self.mcp_status.get(mcp_id, False)
        }
    def set_mcp_enabled(self, mcp_id: str, enabled: bool) -> dict:

    def toggle_mcp(self, mcp_id: str) -> bool:
        """MCP状態切り替え"""
        if mcp_id in self.mcp_status:
            self.mcp_status[mcp_id] = not self.mcp_status[mcp_id]
            return self.mcp_status[mcp_id]
        return False
        """MCP有効/無効設定"""
        if mcp_id in self.mcp_status:
            self.mcp_status[mcp_id] = enabled
        return self.get_mcp_status(mcp_id)
    def get_all_mcp_status(self) -> dict:
        """全MCP状態取得"""
        return {
            mcp_id: self.get_mcp_status(mcp_id)
            for mcp_id in self.available_mcps.keys()
        }
    async def process_with_mcp(self, message: str, mcp_id: str = 'productmaster'):
        """指定MCPでメッセージ処理"""
        import time
        start_time = time.time()
        
        if mcp_id not in self.mcp_clients or not self.mcp_status.get(mcp_id, False):
            return {
                "success": False,
                "error": f"MCP {mcp_id} not available or disabled",
                "debug_info": {
                    "mcp_id": mcp_id,
                    "available": mcp_id in self.mcp_clients,
                    "enabled": self.mcp_status.get(mcp_id, False)
                }
            }
        
        try:
            client = self.mcp_clients[mcp_id]
            result = await client.process_message(message)
            processing_time = round((time.time() - start_time) * 1000, 2)
            
            # debug_infoを追加
            if isinstance(result, dict):
                result["debug_info"] = {
                    "mcp_id": mcp_id,
                    "processing_time_ms": processing_time,
                    "message_length": len(message),
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            
            return result
        except Exception as e:
            processing_time = round((time.time() - start_time) * 1000, 2)
            logger.error(f"MCP {mcp_id} processing error: {e}")
            return {
                "success": False,
                "error": str(e),
                "debug_info": {
                    "mcp_id": mcp_id,
                    "processing_time_ms": processing_time,
                    "error_type": type(e).__name__,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
