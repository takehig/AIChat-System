# AIChat-System 設計書 v2.3.0

## 🎯 ツール単位制御・初期化エラー修正完了（2025-09-19）

### ✅ ツール単位の有効/無効制御実装
**個別ツール制御による柔軟なMCP管理システム**

#### **仕様確定**
- **制御単位**: ツール単位（MCP単位ではない）
- **対象ツール**: 
  - `get_product_details` (ProductMaster)
  - `search_customers_by_bond_maturity` (CRM)
  - `get_customer_holdings` (CRM)
  - `predict_cash_inflow_from_sales_notes` (CRM)
- **UI**: 各ツール個別の有効/無効ボタン

#### **技術実装**
```python
# MCPManager - ツール単位状態管理
class MCPManager:
    def __init__(self):
        self.available_tools: Dict[str, dict] = {}
        self.enabled_tools: set = set()  # ツール単位の状態管理
    
    def toggle_tool(self, tool_name: str) -> bool:
        """ツールの有効/無効を切り替え"""
        if tool_name in self.enabled_tools:
            self.enabled_tools.remove(tool_name)
            return False
        else:
            self.enabled_tools.add(tool_name)
            return True
    
    def get_tool_status(self, tool_name: str) -> bool:
        """個別ツールの状態取得"""
        return tool_name in self.enabled_tools
```

#### **API設計**
```python
# ツール切り替えAPI
@app.post("/api/tools/{tool_name}/toggle")
async def toggle_tool(tool_name: str):
    enabled = ai_agent.mcp_manager.toggle_tool(tool_name)
    return {"status": "success", "tool_name": tool_name, "enabled": enabled}

# ツール状態取得API（個別状態付き）
@app.get("/api/mcp/tools")
async def get_mcp_tools():
    for tool in tools:
        tool["enabled"] = ai_agent.mcp_manager.get_tool_status(tool["name"])
```

#### **フロントエンド実装**
```javascript
// ツール個別状態表示
mcpInfo.tools.forEach(tool => {
    allTools.push({
        name: tool.name,
        enabled: tool.enabled,  // ツール個別の状態を使用
        mcpName: mcpName
    });
});

// ボタン切り替え
async function toggleTool(toolName) {
    const response = await fetch(`/api/tools/${toolName}/toggle`, {method: 'POST'});
    const result = await response.json();
    if (result.status === 'success') {
        updateToolButton(toolName, result.enabled);
    }
}
```

### ✅ 初期化エラー完全修正
**AIAgent・MCPManager統合による安定した初期化**

#### **問題と解決**
```python
# 問題1: AIAgent初期化エラー
# 修正前（エラー）
async def initialize(self):
    for name, client in self.mcp_clients.items():  # ← 存在しない属性
        # ...

# 修正後（正常）
async def initialize(self):
    await self.mcp_manager.initialize()
    await self.mcp_manager.discover_available_tools()
    self.mcp_available = len(self.mcp_manager.mcp_clients) > 0

# 問題2: ツール実行時エラー
# 修正前（エラー）
client = self.mcp_clients[mcp_server_name]  # ← 存在しない属性

# 修正後（正常）
client = self.mcp_manager.mcp_clients[mcp_server_name]  # ← MCPManager参照

# 問題3: uuid インポート不足
# 修正前（エラー）
session_id = request.conversation_id or str(uuid.uuid4())  # ← import uuid なし

# 修正後（正常）
import uuid  # ← インポート追加
session_id = request.conversation_id or str(uuid.uuid4())
```

#### **状態管理統一**
```python
# AIAgent - MCPManagerへの完全委譲
class AIAgent:
    def __init__(self):
        self.mcp_manager = MCPManager()
        
        # StrategyEngineにMCPManager参照を渡す
        self.strategy_engine = StrategyEngine(
            self.bedrock_client, 
            self.mcp_manager.available_tools,  # MCPManagerの辞書を参照
            self.llm_util, 
            self.mcp_manager.enabled_tools     # MCPManagerのsetを参照
        )
    
    # レガシー互換性のためのプロパティ
    @property
    def available_tools(self):
        return self.mcp_manager.available_tools
    
    @property
    def enabled_tools(self):
        return self.mcp_manager.enabled_tools
```

### ✅ 修正履歴・コミット
**GitHub反映済み修正内容**

#### **コミット履歴**
```
1cf0443 [FIX] ai_agent.py 古いmcp_clients参照修正 - ツール実行時エラー解決
44f65d0 [FIX] uuid インポート不足修正 - main.py にimport uuid追加
c503622 [FIX] AIAgent初期化処理修正 - MCPManager使用・古いmcp_clients参照削除
5855ead [FIX] ツール単位の有効/無効制御に修正 - MCPManagerでツール個別状態管理・API統一
689c1bf [FIX] mcp_manager.py 構文エラー修正 - set_mcp_enabled メソッド実装追加
```

#### **修正ファイル**
- `backend/ai_agent.py`: 初期化・ツール実行時の参照修正
- `backend/main.py`: uuid インポート追加・API修正
- `backend/mcp_manager.py`: ツール単位状態管理メソッド追加
- `web/index.html`: ツール個別状態表示修正

### ✅ 動作確認結果
**完全動作確認済み**

#### **初期化ログ（正常）**
```
✅ CRM MCP initialized
✅ ProductMaster MCP initialized
Discovered tool: search_customers_by_bond_maturity from crm
Discovered tool: get_customer_holdings from crm
Discovered tool: predict_cash_inflow_from_sales_notes from crm
Discovered tool: get_product_details from productmaster
MCP integration enabled (2 servers)
```

#### **ツール切り替え（正常）**
```
# 初期状態
get_product_details: False
search_customers_by_bond_maturity: False
get_customer_holdings: False
predict_cash_inflow_from_sales_notes: False

# 切り替え後
get_product_details: True
search_customers_by_bond_maturity: True
get_customer_holdings: True
predict_cash_inflow_from_sales_notes: False
```

#### **ツール実行（正常）**
- **質問**: 「2年以内に満期を迎える債券を保有している顧客の営業メモから想定される入金予測を教えて」
- **結果**: 正常回答（エラーなし）
- **デバッグ情報**: ツール実行結果が正常表示

### 🎯 システム安定性向上
**統合された状態管理による信頼性確保**

#### **設計原則**
- **単一責任**: MCPManagerが全MCP関連状態を管理
- **参照統一**: AIAgentはMCPManagerを参照
- **エラー処理**: 完全参照渡し設計でエラー時情報保持
- **互換性**: レガシーコードとの互換性維持

#### **拡張性**
- **新MCPツール**: MCPManagerに追加するだけで対応
- **状態管理**: 統一されたインターフェース
- **UI更新**: 自動的にツール一覧に反映

### 🌐 アクセス情報
- **AIChat System**: http://44.217.45.24/aichat/
- **機能**: ツール個別切り替え・AI対話・MCP統合
- **状態**: 完全動作・エラーなし

---

## 📋 プロジェクト概要
**AI対話・MCP統合システム - 拡張可能アーキテクチャ**

### 🎯 システム目的
- Amazon Bedrock Claude 3 Sonnet との AI 対話
- Model Context Protocol (MCP) サーバー統合
- 拡張可能な MCP アーキテクチャ
- 金融商品検索・顧客管理・入金予測

## 🏗️ システム構成

### 📊 基本情報
- **リポジトリ**: https://github.com/takehig/AIChat-System
- **サービスポート**: 8002
- **アクセスURL**: http://44.217.45.24/aichat/
- **技術スタック**: Python FastAPI, MCP Protocol, HTML5, JavaScript ES6+

### 🔧 ファイル構造
```
AIChat-System/
├── backend/
│   ├── main.py              # FastAPI メインアプリケーション
│   ├── mcp_manager.py       # MCP サーバー管理・アイコン管理
│   ├── ai_agent.py          # AI エージェント・戦略実行
│   ├── integration_engine.py # 最終応答生成・追記型プロンプト
│   ├── strategy_engine.py   # 戦略立案エンジン
│   ├── models.py           # データモデル定義
│   └── requirements.txt     # Python 依存関係
├── web/
│   └── index.html          # フロントエンド（MCP統合版・アイコン表示）
└── DESIGN.md              # 本設計書
```

## 🔑 主要機能

### ✅ 実装済み機能 (v2.2.0)

#### 1. **AI チャット機能**
- Amazon Bedrock Claude 3 Sonnet 統合
- リアルタイム AI 対話
- チャット履歴管理
- **追記型プロンプト**（プレースホルダー廃止）
- **完全参照渡し設計**（エラー時情報保持）

#### 2. **MCP 統合機能**
- **ProductMaster MCP サーバー連携**（商品検索）
- **CRM MCP サーバー連携**（3ツール）
  - 債券満期検索
  - 顧客保有商品取得
  - **営業メモ入金予測**（新規実装）
- 動的 MCP サーバー管理
- MCP 有効/無効切り替え
- **MCPツールアイコン管理**（確定的マッピング）

#### 3. **拡張可能アーキテクチャ**
- 新規 MCP サーバー追加対応
- プラグイン式 MCP 管理
- 設定ベース MCP 制御
- **確定的アイコンマッピング**
- **プロンプトテンプレート安全化**

## 🎯 営業メモ入金予測MCP (v2.2.0新機能)

### 📋 機能概要
**営業メモから入金予測を抽出するMCPツール**
- **入力**: 顧客ID指定テキスト
- **処理**: 営業メモをLLMで解析し入金予測を抽出
- **出力**: 構造化された入金予測データ

### 🔧 技術実装

#### **3段階処理パターン**
```python
# Stage 1: 引数標準化処理
async def standardize_cash_inflow_prediction_arguments(raw_input: str, tool_debug: Dict) -> Dict[str, Any]

# Stage 2: ビジネスロジック実行
async def execute_cash_inflow_prediction_logic(standardized_params: Dict, tool_debug: Dict) -> List[Dict]

# Stage 3: 結果フォーマット処理
async def format_cash_inflow_prediction_results(predictions: list, user_input: str, tool_debug: Dict) -> str
```

#### **LLMループ処理**
- **複数顧客対応**: 顧客数分のLLM呼び出し
- **並列処理可能**: asyncio対応
- **エラーハンドリング**: 個別顧客のLLM失敗時も継続

#### **システムプロンプト（3個）**
1. `cash_inflow_prediction_pre` - 顧客ID抽出
2. `cash_inflow_prediction_analysis` - 営業メモ解析
3. `cash_inflow_prediction_post` - 結果フォーマット

### 📊 入出力仕様

#### **入力パターン**
- `"顧客ID 1の入金予測"`
- `"山田太郎さんの入金予測"`
- `"全顧客の入金予測"`

#### **出力形式**
```
入金予測分析結果:

顧客ID: 1 (伊東 正雄)
- 予測金額: ¥12,600,000
- 予測時期: 2023年4月頃

顧客ID: 2 (佐藤次郎)
- 入金予測: なし
```

## 🔧 MCPツールアイコン管理 (v2.1.0)

### 📋 確定的アイコンマッピング
```python
# グローバル辞書管理
MCP_TOOL_SYSTEM_MAP = {
    'get_product_details': 'productmaster',                    # 商品詳細取得
    'search_customers_by_bond_maturity': 'crm',               # 債券満期検索
    'get_customer_holdings': 'crm',                           # 顧客保有商品
    'predict_cash_inflow_from_sales_notes': 'crm',           # 入金予測
}

MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      # 📦 商品管理
    'crm': 'fa-users',              # 👥 顧客管理
    'default': 'fa-tool'            # 🔧 デフォルト
}
```

### 🎯 新MCPツール追加手順
1. **辞書登録**: `MCP_TOOL_SYSTEM_MAP` にツール名追加
2. **システム種別追加**: 必要に応じて `MCP_SYSTEM_ICONS` に新種別追加
3. **両側同期**: Python・JavaScript両方に同じ設定

## 🔧 追記型プロンプト実装 (v2.2.0)

### 📋 プレースホルダー廃止
**従来の問題:**
- プレースホルダー `{user_message}`, `{tools_used}` でコードとプロンプトが密結合
- 未定義変数でエラー発生
- プロンプト開発者がコードを意識する必要

**新方式:**
```python
# 追記型プロンプト構築
def build_final_prompt(base_prompt: str, user_message: str, results_summary: str, executed_strategy) -> str:
    system_prompt = base_prompt
    system_prompt += f"\n\nユーザーの質問: {user_message}"
    system_prompt += f"\n\n実行したツール: {tools_used_text}"
    system_prompt += f"\n\n実行結果:\n{results_summary}"
    system_prompt += f"\n\n実行時間: {total_execution_time}ms"
    return system_prompt
```

### 🎯 改善効果
- **疎結合化**: コードとプロンプトの完全分離
- **エラー耐性**: 未定義変数エラーなし
- **開発自由度**: プロンプト開発者が自由に記述可能
- **フォールバック統一**: 正常系・エラー系で同じ追記処理

## 🔧 完全参照渡し設計 (v2.1.0)

### 📋 エラー時情報保持強化
**従来の問題:**
- エラー発生時にデバッグ情報が消失
- 戻り値ベースで情報が破棄される

**新設計:**
```python
# Try外でインスタンス作成（エラー時情報保持）
executed_strategy = DetailedStrategy(steps=[])

try:
    # 段階的処理（全て参照渡し）
    await self.strategy_engine.plan_strategy(user_message, executed_strategy)
    await self.execute_detailed_strategy(executed_strategy, user_message)
    await self.integration_engine.generate_final_response(user_message, executed_strategy)
except Exception as e:
    return {
        "strategy": executed_strategy,  # 途中まで実行された情報保持
        "error": str(e)
    }
```

### 🎯 改善効果
- **エラー時デバッグ**: 途中まで実行された全情報を保持
- **段階特定**: どの段階でエラーが発生したかが明確
- **情報継続性**: エラー時もMCP呼び出し結果・LLMプロンプト確認可能

## 🔧 MCP サーバー構成

### 📊 接続MCP一覧
| MCP サーバー | ポート | ツール数 | 機能 |
|-------------|--------|----------|------|
| **ProductMaster MCP** | 8003 | 1 | 商品検索 |
| **CRM MCP** | 8004 | 3 | 顧客管理・入金予測 |

### 🎯 CRM MCP ツール詳細
1. **search_customers_by_bond_maturity**
   - 債券満期日条件で顧客検索
   - アイコン: 👥 (fa-users)

2. **get_customer_holdings**
   - 顧客の保有商品情報取得
   - アイコン: 👥 (fa-users)

3. **predict_cash_inflow_from_sales_notes** ⭐新規
   - 営業メモから入金予測抽出
   - アイコン: 👥 (fa-users)

## 🔧 技術アーキテクチャ

### 📊 処理フロー
```
1. ユーザー入力 → AIChat Frontend
2. AI Agent → 戦略立案 (strategy_engine.py)
3. MCP呼び出し → 各MCPサーバー
4. 結果統合 → 最終応答生成 (integration_engine.py)
5. 追記型プロンプト → Claude 3 Sonnet
6. 応答表示 → Frontend
```

### 🎯 エラーハンドリング
- **完全参照渡し**: エラー時も情報保持
- **段階的デバッグ**: 各段階の実行状況確認可能
- **プロンプト安全化**: 未定義変数エラー防止

## 🔧 開発・運用

### 📋 デプロイ手順
1. **GitHub更新**: ローカル → GitHub
2. **EC2反映**: GitHub → EC2
3. **サービス再起動**: systemctl restart aichat
4. **動作確認**: エンドポイント疎通確認

### 🎯 監視・ログ
- **サービスログ**: journalctl -u aichat
- **MCP通信ログ**: [MCP DEBUG] プレフィックス
- **デバッグ情報**: 完全なstrategy情報表示

## 📊 バージョン履歴

### v2.2.0 (2025-09-19)
- ✅ 営業メモ入金予測MCP実装
- ✅ 追記型プロンプト実装（プレースホルダー廃止）
- ✅ プロンプトテンプレート安全化
- ✅ get_customer_holdings インポートエラー修正

### v2.1.0 (2025-09-19)
- ✅ MCPツールアイコン管理実装
- ✅ 完全参照渡し設計実装
- ✅ エラー時情報保持強化

### v2.0.0 (2025-09-17)
- ✅ CRM MCP統合
- ✅ 債券満期検索・顧客保有商品取得

### v1.0.0 (2025-08-30)
- ✅ 基本AI対話機能
- ✅ ProductMaster MCP統合

## 🎯 今後の拡張予定

### 🔮 Phase 3: 高度な分析機能
- **入金予測精度向上**: 機械学習モデル統合
- **リスク分析MCP**: ポートフォリオリスク評価
- **市場データMCP**: リアルタイム市場情報

### 🔮 Phase 4: 運用最適化
- **パフォーマンス監視**: MCP応答時間監視
- **自動スケーリング**: 負荷に応じたMCP拡張
- **A/Bテスト**: プロンプト最適化

**設計書更新完了 - 営業メモ入金予測MCP実装・追記型プロンプト・アイコン管理を反映**
