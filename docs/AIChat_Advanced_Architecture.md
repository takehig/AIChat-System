# AIChat System - 高度なアーキテクチャ詳細

## 🧠 MCP戦略エンジンの実装詳細

### 戦略立案プロセス
```python
async def plan_detailed_strategy(self, user_message: str) -> DetailedStrategy:
    """
    1. 利用可能ツール分析
    2. クエリ要求内容特定
    3. 必要最小限ツール選択
    4. 実行順序決定
    5. JSON形式戦略出力
    """
```

### 戦略判定ルール
- **明示的要求のみ**: ユーザーが要求していない情報は取得しない
- **最小限原則**: 必要最小限のツールのみ選択
- **動的選択**: 利用可能ツールから適切なものを選択
- **無駄排除**: 複数ツールの無駄な組み合わせを避ける

## 🔗 結果統合エンジンの実装

### 統合処理フロー
```python
async def execute_detailed_strategy(self, strategy: DetailedStrategy, user_message: str):
    """
    1. 各ステップを順次実行
    2. 前ステップ結果を次ステップで活用
    3. 実行時間・デバッグ情報記録
    4. エラーハンドリング
    5. 統合結果生成
    """
```

### 動的システムプロンプト生成
```python
async def generate_contextual_response_with_strategy(self, user_message: str, executed_strategy: DetailedStrategy):
    """
    1. MCP実行結果を分析
    2. 動的にシステムプロンプト構築
    3. コンテキスト情報統合
    4. Claude呼び出しで最終回答生成
    """
```

## 🛠️ 複数MCPサーバー管理

### 動的ツール発見
```python
async def discover_available_tools(self):
    """
    1. 全MCPサーバーをスキャン
    2. 各サーバーからツール情報収集
    3. ツールルーティング情報構築
    4. 有効/無効状態管理
    """
```

### ツール実行ルーティング
```python
# 実装済み機能:
self.mcp_clients = {
    'productmaster': MCPClient("http://localhost:8003"),
    'crm': MCPClient("http://localhost:8004")
}
self.tool_routing = {}  # ツール名 → MCPサーバー名
```

## 📊 詳細実行ログ・デバッグ機能

### 実行情報記録
```python
@dataclass
class DetailedStep:
    step: int
    tool: str
    reason: str
    input: Optional[str] = None
    output: Optional[Dict] = None
    execution_time_ms: Optional[float] = None
    debug_info: Optional[Dict] = None
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None
    llm_execution_time_ms: Optional[float] = None
```

### 戦略実行追跡
```python
@dataclass  
class DetailedStrategy:
    steps: List[DetailedStep]
    strategy_llm_prompt: Optional[str] = None
    strategy_llm_response: Optional[str] = None
    strategy_llm_execution_time_ms: Optional[float] = None
```

## 🎯 実際の処理フロー例

### 複雑クエリ: "田中さんにおすすめの社債は？"

#### 1. 戦略立案フェーズ
```json
{
  "steps": [
    {"step": 1, "tool": "customer_search", "reason": "田中さんの顧客情報取得"},
    {"step": 2, "tool": "product_search", "reason": "社債商品検索"}
  ]
}
```

#### 2. 実行フェーズ
```python
# Step 1: CRM MCP → 顧客情報取得
customer_data = await crm_client.call_tool("customer_search", {"name": "田中"})

# Step 2: ProductMaster MCP → 社債検索（顧客プロファイル考慮）
products = await product_client.call_tool("product_search", {
    "type": "bond", 
    "customer_profile": customer_data
})
```

#### 3. 統合・回答生成フェーズ
```python
# 動的システムプロンプト構築
system_prompt = f"""
顧客情報: {customer_data}
適合商品: {products}
上記を基に個別化された投資提案を生成してください。
"""

# Claude呼び出し
final_response = await claude_client.generate(system_prompt, user_message)
```

## 🔧 エラーハンドリング・フォールバック

### MCP障害時の対応
```python
try:
    if await client.health_check():
        result = await client.call_tool(tool_name, arguments)
    else:
        # フォールバック: 他のMCPまたは通常AI応答
        result = await fallback_strategy(tool_name, arguments)
except Exception as e:
    # エラーログ記録 + 代替手段実行
    logger.error(f"MCP execution failed: {e}")
    result = await alternative_approach(user_message)
```

## 📈 パフォーマンス最適化

### 並列実行対応
```python
# 独立したツールは並列実行
if can_execute_parallel(strategy.steps):
    tasks = [execute_step(step) for step in strategy.steps]
    results = await asyncio.gather(*tasks)
else:
    # 依存関係がある場合は順次実行
    results = await execute_sequential(strategy.steps)
```

### キャッシュ機能
```python
# 同一クエリのキャッシュ（将来実装）
cache_key = generate_cache_key(user_message, enabled_tools)
if cached_result := await get_cache(cache_key):
    return cached_result
```

---

**この詳細アーキテクチャが既に実装済みであることが判明しました。**
