# MCP拡張アーキテクチャ設計書

## 概要
AIChat システムに複数MCP対応の拡張可能なアーキテクチャを実装

## 🚨 MCPResponse標準仕様（重要）

### ✅ 必須MCPResponse構造
```python
# models.py - 標準MCPResponse定義
class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Any = None                              # メイン結果データ
    error: Optional[str] = None                     # エラーメッセージ
    debug_response: Optional[Dict[str, Any]] = None # デバッグ情報（スキーマレス）
```

### ✅ 正しい使用例
```python
# ✅ 正しい実装
return MCPResponse(
    result={
        "content": [{"type": "text", "text": "結果テキスト"}],
        "isError": False
    },
    debug_response={  # ← 正しいフィールド名
        "function_name": "tool_name",
        "input_params": params,
        "step1_process": {...},
        "step2_process": {...},
        "execution_time_ms": 1234,
        "error": None
    }
)
```

### ❌ 間違った実装例
```python
# ❌ 間違い - 存在しないフィールド使用
return MCPResponse(
    content=[...],           # ← 存在しない
    isError=False,           # ← 存在しない
    _meta={"debug_info": ...} # ← 存在しない
)
```

### 🎯 debug_response設計原則

#### **スキーマレス設計**
- **柔軟性**: ツール毎に異なるデバッグ情報構造を許可
- **拡張性**: 新しいデバッグ情報を自由に追加可能
- **統一性**: 基本的なフィールド（function_name, execution_time_ms等）は統一

#### **推奨デバッグ情報構造**
```python
debug_response = {
    "function_name": "tool_function_name",
    "input_params": {...},           # 入力パラメータ
    "step1_xxx": {                   # 処理段階毎の情報
        "llm_request": "...",        # LLMリクエスト（結合済み文字列）
        "llm_response": "...",       # LLMレスポンス
        "execution_time_ms": 123,    # 実行時間
        "result": {...}              # 段階結果
    },
    "step2_xxx": {...},
    "total_execution_time_ms": 1234, # 総実行時間
    "error": None                    # エラー情報
}
```

### 🔄 AIChat統合フロー
```python
# 1. MCPサーバー → AIChatへのレスポンス
mcp_response = MCPResponse(
    result={"content": [...], "isError": False},
    debug_response=tool_debug  # ← MCPサーバーが生成
)

# 2. AIChat mcp_client.py での変換
debug_info["response"]["tool_debug"] = mcp_dict.get("debug_response")
response = {
    "result": mcp_dict["result"],
    "debug_info": debug_info  # ← AIChatの統一フォーマット
}
```

## システム構成

### 現在の実装
- **ProductMaster MCP**: 商品情報検索 (Port 8003)
- **CRM MCP**: 顧客検索・保有商品 (Port 8004)
- **拡張可能設計**: 新しいMCPを簡単に追加可能

### アーキテクチャ図
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend       │    │   MCP Servers   │
│                 │    │                  │    │                 │
│ ProductMaster   │◄──►│   MCPManager     │◄──►│ ProductMaster   │
│ MCP Button      │    │                  │    │ (Port 8003)     │
│                 │    │   AIAgent        │    │                 │
│ CRM MCP Button  │    │                  │    │ CRM MCP         │
│                 │    │                  │    │ (Port 8004)     │
│ [Future MCPs]   │    │                  │    │ [Future MCPs]   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 実装詳細

### 1. フロントエンド (web/index.html)

#### MCPツールアイコン管理
```javascript
// グローバル辞書管理
const MCP_TOOL_SYSTEM_MAP = {
    'get_product_details': 'productmaster',
    'search_products_by_name_fuzzy': 'productmaster',
    'search_customers_by_bond_maturity': 'crm',
    'get_customer_holdings': 'crm',
};

const MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      // 📦 商品管理
    'crm': 'fa-users',              // 👥 顧客管理
    'default': 'fa-tool'            // 🔧 デフォルト
};

// 確定的アイコン表示
function getToolIcon(toolName) {
    const systemType = MCP_TOOL_SYSTEM_MAP[toolName] || 'default';
    return MCP_SYSTEM_ICONS[systemType] || MCP_SYSTEM_ICONS['default'];
}
```

#### MCP状態管理
```javascript
// 明示的なMCP名表示
btn.textContent = 'ProductMaster MCP: ON/OFF/無効/エラー'

// API呼び出し
fetch('/aichat/api/status')
fetch('/aichat/api/mcp/toggle')
```

### 2. バックエンド (backend/)

#### MCPManager (mcp_manager.py)
```python
class MCPManager:
    available_mcps = {
        'productmaster': {
            'name': 'ProductMaster',
            'description': '商品情報検索MCP',
            'url': 'http://localhost:8003',
            'enabled': False
        },
        'crm': {
            'name': 'CRM',
            'description': '顧客管理MCP',
            'url': 'http://localhost:8004',
            'enabled': False
        }
        # 将来の拡張用
        # 'market_data': { ... }
    }
```

#### AIAgent (ai_agent.py)
```python
class AIAgent:
    def __init__(self):
        self.mcp_manager = MCPManager()
        self.mcp_available = False
        self.mcp_enabled = False  # ProductMaster MCP状態
```

### 3. API エンドポイント
- `GET /api/status`: MCP状態取得
- `POST /api/mcp/toggle`: ProductMaster MCP オンオフ切り替え

## 拡張方法

### 新しいMCP追加手順
1. **MCPサーバー起動**: 新しいポートで起動
2. **mcp_manager.py更新**: `available_mcps`に設定追加
3. **フロントエンド更新**: 必要に応じてUI追加
4. **systemd設定**: enterprise-systemdに追加

### 例: MarketData MCP追加
```python
# mcp_manager.py
'market_data': {
    'name': 'MarketData', 
    'description': '市場データ取得MCP',
    'url': 'http://localhost:8004',
    'enabled': False
}
```

## デバッグ機能
- **JavaScript**: `[MCP DEBUG]` プレフィックス付きログ
- **Python**: 詳細なMCP初期化・処理ログ
- **API**: リクエスト・レスポンスログ

## 問題解決履歴

### 主要な問題と解決
1. **JavaScript APIパス**: 相対パス → 絶対パス (`/aichat/api/status`)
2. **updateMCPButton関数**: 空実装 → 完全実装
3. **API応答**: `mcp_enabled`フィールド不足 → 追加
4. **構文エラー**: 括弧不整合 → 修正
5. **MCPResponse構造**: `_meta` → `debug_response` 修正（2025-09-19）

### デバッグ手法確立
- 段階的トラブルシュート
- 詳細ログ出力
- ブラウザコンソール活用

## 今後の拡張予定
- MarketData MCP (市場データ取得)
- NewsAnalysis MCP (ニュース分析)
- RiskAssessment MCP (リスク評価)

## 技術スタック
- **Frontend**: HTML5, JavaScript ES6+, Bootstrap 5
- **Backend**: Python FastAPI, asyncio
- **MCP**: Model Context Protocol
- **Database**: PostgreSQL (ProductMaster, CRM)
- **Deployment**: systemd, Nginx proxy

## 更新履歴
- 2025-08-30: 初版作成、ProductMaster MCP実装完了
- 2025-09-19: MCPResponse標準仕様追加、debug_response構造明文化
