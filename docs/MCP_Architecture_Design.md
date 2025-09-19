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

## 🎯 推奨デバッグ情報構造（最重要）

### ✅ 標準debug_response構造
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
    "step2_xxx": {
        "sql_query": "...",          # SQL実行の場合
        "sql_parameters": [...],     # SQLパラメータ
        "execution_time_ms": 45,
        "result": {...}
    },
    "step3_xxx": {...},
    "total_execution_time_ms": 1234, # 総実行時間
    "error": None                    # エラー情報
}
```

### ✅ Try外側でのデバッグ情報初期化（必須）
```python
async def mcp_tool_function(params):
    start_total_time = time.time()
    
    # Try外側でデバッグ情報初期化（推奨構造）
    debug_response = {
        "function_name": "mcp_tool_function",
        "input_params": params,
        "step1_process": {
            "llm_request": None,
            "llm_response": None,
            "execution_time_ms": 0,
            "result": None
        },
        "step2_sql": {
            "sql_query": None,
            "sql_parameters": None,
            "execution_time_ms": 0,
            "result": None
        },
        "total_execution_time_ms": 0,
        "error": None
    }
    
    try:
        # 処理実装...
        return {"result": result, "debug_info": debug_response}
    except Exception as e:
        debug_response["error"] = str(e)
        debug_response["total_execution_time_ms"] = int((time.time() - start_total_time) * 1000)
        return {"error": f"処理中にエラーが発生しました: {str(e)}", "debug_info": debug_response}
```

## 🚨 MCPツール命名・説明ルール（重要）

### ✅ ツール名命名規則
- **簡潔性**: 機能が一目で分かる短い名前
- **一貫性**: 動詞_対象_条件 パターン
- **例**: `get_customers_by_product` (良い) vs `get_customers_by_product_text` (冗長)

### ✅ 説明文ルール
- **簡潔性**: 核心機能のみを1文で記述
- **戦略性**: AIエージェントの判断に必要な情報のみ
- **技術詳細禁止**: 処理段階・実装詳細は説明文に含めない

```python
# ✅ 良い説明文
"description": "商品IDを含むテキストから該当商品の保有顧客リストを返すツール"

# ❌ 悪い説明文（技術詳細含む）
"description": "入力テキストから商品IDを抽出し、該当商品の保有顧客リストを返すツール。処理は3段階：1)LLMによるテキストからのID抽出、2)SQLによる顧客データ検索、3)LLMによる結果整形。"
```

## 🔧 AIChat統合必須手順

### ✅ mcp_manager.py 辞書登録（必須）
```python
# backend/mcp_manager.py - 新ツール追加時は必ず登録
MCP_TOOL_SYSTEM_MAP = {
    # CRM MCP ツール
    'search_customers_by_bond_maturity': 'crm',
    'get_customer_holdings': 'crm',
    'get_customers_by_product': 'crm',  # ← 新規追加時は必須
}
```

### ✅ アイコン自動適用
```python
MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      # 📦 商品管理
    'crm': 'fa-users',              # 👥 顧客管理
    'default': 'fa-tool'            # 🔧 デフォルト
}
```

## 🎯 3段階LLM処理パターン（実装済み）

### ✅ 標準3段階処理フロー
```python
# STEP 1: 非正規テキスト → パラメータ化（LLM）
# STEP 2: パラメータ → SQL実行 → 構造化データ
# STEP 3: 構造化データ → 整形された非正規テキスト（LLM）
```

### ✅ 実装例：商品保有顧客抽出ツール
```python
# CRM MCP: get_customers_by_product
# SystemPrompts:
# - customer_by_product_extract_ids     (STEP1: ID抽出)
# - customer_by_product_format_results  (STEP3: 結果整形)

# 処理フロー:
# 入力: "検索結果: 2件\n1. Apple Inc. (ID: 6)\n2. Tesla Inc. (ID: 10)"
# STEP1: [6, 10] 抽出
# STEP2: SQL実行で顧客データ取得
# STEP3: 商品別顧客リスト整形
```

## 🚨 SystemPrompt管理ルール（重要）

### ✅ **SystemPrompt取得統一実装（最重要）**
```python
# 必須: 既存の統一実装を使用
from utils.system_prompt import get_system_prompt

# 統一API仕様
# URL: http://localhost:8002/api/system-prompts/{prompt_key}
# ライブラリ: httpx
# 実装場所: utils/system_prompt.py

# 正しい使用方法
system_prompt = await get_system_prompt("prompt_key")

# 禁止事項
❌ 独自のget_system_prompt関数作成禁止
❌ aiohttp等の別ライブラリ使用禁止  
❌ 直接SystemPrompt Management API呼び出し禁止
❌ 直接データベースアクセス禁止
```

### ✅ **LLM呼び出し統一実装（最重要）**
```python
# 必須: 既存の統一実装を使用
from utils.llm_util import llm_util

# 統一API仕様
# モデル: anthropic.claude-3-sonnet-20240229-v1:0
# ライブラリ: boto3
# 実装場所: utils/llm_util.py

# 正しい使用方法
response = await llm_util.call_claude(system_prompt, user_input)

# 禁止事項
❌ 独自のLLM呼び出し関数作成禁止
❌ boto3直接使用禁止
❌ aiohttp等の別ライブラリ使用禁止
❌ 直接Bedrock API呼び出し禁止
```

### ✅ **utils/ディレクトリ使用義務（最重要）**
```python
# 必須: utils/ ディレクトリの共通ライブラリ確認・使用
- utils/system_prompt.py: SystemPrompt取得
- utils/llm_util.py: LLM呼び出し
- utils/database.py: データベース接続

# 禁止: 同じ機能の独自実装
❌ 既存機能の独自実装禁止
❌ 重複ライブラリ作成禁止
```

### ✅ **新ライブラリ使用時の確認ルール（必須）**
1. **既存実装確認**: 同じ機能の既存実装がないか必ず確認
2. **utils/ディレクトリ確認**: 共通ライブラリが存在しないか確認
3. **統一性確認**: 他のMCPツールでの実装方法を確認
4. **事前相談**: 新ライブラリ使用前にユーザーに確認

### ✅ 日本語プロンプト登録の正しい方法
```bash
# 直接SQL方式（文字化けしない・CRLF改行）
sudo -u postgres psql -d aichat -c "INSERT INTO system_prompts (prompt_key, prompt_text, created_at, updated_at) VALUES ('プロンプトキー', '日本語プロンプト内容\r\n\r\n## セクション\r\n内容', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);"
```

### ❌ 避けるべき方法
```bash
# curl POST方式（文字化けする・LF改行）
curl -X POST http://localhost:8007/create -d "prompt_key=test&prompt_text=日本語内容"
```

### ✅ プロンプトキー命名規則
- **ツール固有**: `{ツール名}_{処理段階}` 形式
- **例**: `customer_by_product_extract_ids`, `customer_by_product_format_results`

## 🎯 データベース直接操作作法（必須）

### ✅ 改行コード指定ルール
- **CRLF使用**: `\r\n` でWindows互換改行
- **エスケープ注意**: SSM経由では `\r\n` を直接指定（`\\r\\n` は二重エスケープで文字列化）
- **ブラウザ表示**: CRLFで正常な改行表示

### ✅ 文字エンコーディング対応
- **直接SQL**: UTF-8で正常保存
- **curl POST**: SystemPrompt Management側でエンコーディング問題発生
- **ブラウザ登録**: UTF-8で正常保存

### ✅ データベース操作の優先順位
1. **ブラウザ登録**: 最も安全（UTF-8 + CRLF）
2. **直接SQL**: 確実（UTF-8 + 指定改行コード）
3. **curl POST**: 問題あり（文字化け + LF改行）

## 🚨 エラーハンドリング設計原則（重要）

### ✅ フォールバック処理禁止ルール
- **🔥 勝手なフォールバック処理絶対禁止**: エラー時に勝手にフォールバック処理を追加してはならない
- **🔥 「安全のため」フォールバック禁止**: 「安全のため」「念のため」を理由にしたフォールバック処理は一切禁止

### ✅ 正しいエラーハンドリング
```python
except Exception as e:
    debug_response["error"] = str(e)
    debug_response["total_execution_time_ms"] = int((time.time() - start_total_time) * 1000)
    return {"error": f"処理中にエラーが発生しました: {str(e)}", "debug_info": debug_response}
```

### ❌ 禁止されたフォールバック例
```python
# ❌ 禁止 - 勝手なフォールバック処理
except Exception as e:
    # 安全のためデフォルト値を返す ← 禁止
    return {"result": "デフォルト結果", "debug_info": debug_response}
```

## 🎯 MCP開発標準手順

### STEP 0: 既存実装確認（必須）
```python
# 新ツール開発前に必ず確認
1. utils/ ディレクトリの共通ライブラリ確認
   - utils/system_prompt.py: SystemPrompt取得
   - utils/llm_util.py: LLM呼び出し
   - utils/database.py: データベース接続
2. 他のMCPツールでの実装方法確認
3. 統一実装の存在確認
4. 新ライブラリ使用前のユーザー相談

# 禁止事項
❌ utils/ 確認なしでの開発開始禁止
❌ 既存実装確認なしでの独自実装禁止
❌ 統一実装があるのに独自実装作成禁止
```

### STEP 1: SystemPrompt作成
```bash
# 直接SQL方式でUTF-8・CRLF対応
sudo -u postgres psql -d aichat -c "INSERT INTO system_prompts..."
```

### STEP 2: MCPツール実装
```python
# tools_config.json にツール定義追加
# tools/{module}.py に実装
# 推奨デバッグ構造準拠
```

### STEP 3: AIChat統合
```python
# mcp_manager.py 辞書登録（必須）
MCP_TOOL_SYSTEM_MAP = {
    'new_tool_name': 'system_type',
}
```

### STEP 4: GitHub反映・デプロイ
```bash
# 各リポジトリでコミット・プッシュ
# EC2でgit pull・サービス再起動
```

### STEP 5: 動作確認
```bash
# ツール一覧確認
curl -s http://localhost:8004/mcp -d '{"method": "tools/list"}'
# AIChat統合確認
curl -s http://localhost/aichat/api/status
```

## 🎯 実装済みMCPツール一覧

### ProductMaster MCP (Port 8003)
- `get_product_details`: 商品詳細取得
- `search_products_by_name_fuzzy`: 商品名曖昧検索

### CRM MCP (Port 8004)
- `search_customers_by_bond_maturity`: 債券満期顧客検索
- `get_customer_holdings`: 顧客保有商品取得
- `predict_cash_inflow_from_sales_notes`: 営業メモ入金予測
- `get_customers_by_product`: 商品保有顧客抽出 ← 新規実装

## 🚨 重要な禁止事項

### ファイル管理
- **🔥 別名ファイル作成絶対禁止**: `main_new.py`, `test_*.py` 等の別名ファイル作成禁止
- **🔥 バックアップファイル禁止**: `*.backup`, `*.old` 等のバックアップファイル作成禁止

### データベース管理
- **🔥 データベース設定変更禁止**: PostgreSQLのユーザー・パスワード変更禁止
- **🔥 ALTER USER実行禁止**: データベース側設定変更は一切禁止

### 独断専行防止
- **🔥 エラー時の勝手な対処禁止**: ユーザーの許可なく勝手に「修正」してはならない
- **🔥 設定ファイル勝手変更禁止**: 認証情報、設定値を独断で変更禁止

## 🎯 今後の拡張予定

### 計画中のMCPツール
- **MarketData MCP**: 市場データ取得・分析
- **News MCP**: ニュース情報取得・要約
- **Risk MCP**: リスク分析・評価

### 拡張アーキテクチャの利点
- **統一インターフェース**: 全MCPで共通のデバッグ構造
- **簡単拡張**: 新MCPツール追加が容易
- **保守性**: 標準化されたコード構造
- **デバッグ性**: 完全なトレーサビリティ

---

**この設計書に従うことで、一貫性のある高品質なMCPツールの開発・運用が可能になります。**
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
