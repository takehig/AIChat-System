import logging
import aiohttp
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MCPTool:
    """MCP ツール情報"""
    tool_key: str
    tool_name: str
    description: str
    mcp_server_name: str
    remarks: Optional[str] = None
    enabled: bool = True
    available: bool = False  # 実際にAPIが稼働しているか

class MCPToolManager:
    """AIChat MCP ツール管理クラス"""
    
    def __init__(self, mcp_management_url: str = "http://localhost:8008"):
        self.mcp_management_url = mcp_management_url
        self.registered_tools: Dict[str, MCPTool] = {}  # DB登録済みツール
        self.enabled_tools: set = set()  # Enable状態のツール
        
    async def initialize(self):
        """初期化: 1.DB読み込み → 2.ステータスチェック → 3.Enable管理"""
        logger.info("MCP Tool Manager 初期化開始")
        
        # STEP 1: テーブルからツール情報読み込み
        await self._load_registered_tools()
        
        # STEP 2: 実際のAPI稼働状況チェック
        await self._check_tool_availability()
        
        # STEP 3: Enable状態初期化（デフォルト全有効）
        self._initialize_enabled_status()
        
        logger.info(f"MCP Tool Manager 初期化完了: {len(self.registered_tools)}個のツール登録済み")
    
    async def _load_registered_tools(self):
        """STEP 1: MCP-Management DB からツール情報読み込み"""
        logger.info("DB登録済みツール読み込み中...")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.mcp_management_url}/api/tools") as response:
                    if response.status == 200:
                        mcp_tools = await response.json()
                        
                        for tool_data in mcp_tools:
                            tool = MCPTool(
                                tool_key=tool_data.get('tool_key'),
                                tool_name=tool_data.get('tool_name'),
                                description=tool_data.get('description'),
                                mcp_server_name=tool_data.get('mcp_server_name', 'Unknown'),
                                remarks=tool_data.get('remarks'),
                                enabled=True,  # デフォルト有効
                                available=False  # ステータスチェック前は未確認
                            )
                            self.registered_tools[tool.tool_key] = tool
                        
                        logger.info(f"DB から {len(self.registered_tools)} 個のツールを読み込み")
                    else:
                        logger.error(f"MCP-Management DB読み込みエラー: HTTP {response.status}")
        except Exception as e:
            logger.error(f"DB読み込み失敗: {e}")
    
    async def _check_tool_availability(self):
        """STEP 2: 登録済みツールの実際の稼働状況チェック"""
        logger.info("ツール稼働状況チェック中...")
        
        # MCP Server別にAPIチェック
        server_urls = {
            'ProductMaster MCP': 'http://localhost:8003/tools/descriptions',
            'CRM MCP': 'http://localhost:8004/tools/descriptions'
        }
        
        for server_name, url in server_urls.items():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                        if response.status == 200:
                            # 該当サーバーのツールを available=True に設定
                            for tool in self.registered_tools.values():
                                if tool.mcp_server_name == server_name:
                                    tool.available = True
                            logger.info(f"{server_name}: 稼働中")
                        else:
                            logger.warning(f"{server_name}: HTTP {response.status}")
            except Exception as e:
                logger.warning(f"{server_name}: 接続失敗 - {e}")
    
    def _initialize_enabled_status(self):
        """STEP 3: Enable状態初期化"""
        # デフォルト: 稼働中のツールのみ有効
        self.enabled_tools = {
            tool_key for tool_key, tool in self.registered_tools.items() 
            if tool.available
        }
        logger.info(f"Enable状態初期化: {len(self.enabled_tools)}個のツールが有効")
    
    def get_all_tools(self) -> Dict[str, MCPTool]:
        """全登録ツール取得"""
        return self.registered_tools.copy()
    
    def get_enabled_tools(self) -> Dict[str, MCPTool]:
        """有効ツールのみ取得"""
        return {
            tool_key: tool for tool_key, tool in self.registered_tools.items()
            if tool_key in self.enabled_tools
        }
    
    def is_tool_enabled(self, tool_key: str) -> bool:
        """ツール有効状態確認"""
        return tool_key in self.enabled_tools
    
    def toggle_tool_enabled(self, tool_key: str) -> bool:
        """ツール有効/無効切り替え"""
        if tool_key not in self.registered_tools:
            return False
        
        if tool_key in self.enabled_tools:
            self.enabled_tools.remove(tool_key)
            enabled = False
        else:
            self.enabled_tools.add(tool_key)
            enabled = True
        
        logger.info(f"ツール {tool_key}: {'有効' if enabled else '無効'}")
        return enabled
    
    def get_tools_by_server(self, server_name: str) -> Dict[str, MCPTool]:
        """MCP Server別ツール取得"""
        return {
            tool_key: tool for tool_key, tool in self.registered_tools.items()
            if tool.mcp_server_name == server_name
        }
