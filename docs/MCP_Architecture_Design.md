# MCP統一アーキテクチャ設計書 v2.2.0

## 🎯 統一アーキテクチャ概要

### ✅ 一元管理システム
```
MCP-Management データベース (aichat.mcp_tools)
    ↓ HTTP API
AIChat MCPToolManager (class MCPTool 辞書化)
    ↓ 共有インスタンス
全モジュール (ai_agent.py, strategy_engine.py, etc.)
```

### ✅ データフロー
```
1. MCP-Management: ツール情報をDBで管理
2. AIChat MCPToolManager: 起動時にDB読み込み → MCPTool インスタンス化
3. 全モジュール: MCPToolManager.registered_tools 辞書を共有
4. CRM-MCP等: 独自設定ファイル廃止 → MCP-Management API参照
```

## 🔧 技術実装

### ✅ MCPTool クラス設計
```python
@dataclass
class MCPTool:
    tool_key: str           # 一意識別子
    tool_name: str          # 表示名
    description: str        # 説明
    mcp_server_name: str    # サーバー名
    system_prompt: str      # システム指示
    enabled: bool           # 有効/無効
    available: bool         # 実際の稼働状況
    
    def to_dict(self) -> Dict[str, Any]  # 辞書変換
    def from_dict(cls, data) -> MCPTool  # 辞書から復元
```

### ✅ MCPToolManager 初期化フロー
```python
async def initialize(self):
    # STEP 1: MCP-Management DB読み込み
    await self._load_registered_tools()
    
    # STEP 2: 実際の稼働状況チェック
    await self._check_tool_availability()
    
    # STEP 3: enabled=True かつ available=True のみ有効化
    self._update_enabled_status()
```

### ✅ 共有辞書アクセスパターン
```python
# 全モジュール共通アクセス方法
mcp_tool_manager = MCPToolManager()
await mcp_tool_manager.initialize()

# ツール情報取得
tool = mcp_tool_manager.registered_tools.get("tool_key")
if tool and tool.enabled and tool.available:
    # ツール使用可能
```

## 🚨 重要な設計原則

### ✅ 一元管理の徹底
- **唯一の真実**: MCP-Management データベースのみ
- **設定ファイル廃止**: tools_config.json 等の独自設定ファイル使用禁止
- **API統一**: 全MCPサーバーはMCP-Management API参照

### ✅ 辞書化統一
- **MCPTool.to_dict()**: 全データ交換で辞書形式使用
- **型安全性**: MCPTool クラスで型チェック
- **変換統一**: from_dict() で一貫した復元

### ✅ 非同期初期化
- **initialize() 必須**: 全モジュールで初期化実行
- **DB読み込み**: HTTP API経由でMCP-Management接続
- **稼働確認**: 実際のMCPサーバー疎通確認

## 🛡️ 防御的プログラミング実装 (v2.2.0 更新)

### ✅ LLM呼び出し防御構文統一
**全MCPツールの llm_util.py に防御構文実装完了**

#### **CRM-MCP**
```python
async def call_claude(self, system_prompt: str, user_message: str, ...):
    # 防御構文: どんな入力でも文字列に変換
    if not isinstance(system_prompt, str):
        system_prompt = str(system_prompt)
    if not isinstance(user_message, str):
        user_message = str(user_message)
```

#### **ProductMaster-MCP**
```python
async def call_claude(self, system_prompt: str, user_message: str, ...):
    # 防御構文: どんな入力でも文字列に変換
    if not isinstance(system_prompt, str):
        system_prompt = str(system_prompt)
    if not isinstance(user_message, str):
        user_message = str(user_message)

async def call_llm_simple(self, full_prompt: str, ...):
    # 防御構文: どんな入力でも文字列に変換
    if not isinstance(full_prompt, str):
        full_prompt = str(full_prompt)
```

#### **AIChat**
```python
async def call_claude(self, system_prompt: str, user_message: str, ...):
    # 防御構文: どんな入力でも文字列に変換
    if not isinstance(system_prompt, str):
        system_prompt = str(system_prompt)
    if not isinstance(user_message, str):
        user_message = str(user_message)

async def call_claude_with_llm_info(self, system_prompt: str, user_message: str, ...):
    # 防御構文: どんな入力でも文字列に変更
    if not isinstance(system_prompt, str):
        system_prompt = str(system_prompt)
    if not isinstance(user_message, str):
        user_message = str(user_message)
```

### ✅ 防御構文の効果
- **ValidationException 根本的防止**
- **どんな入力でも文字列に変換**
- **統一的なエラー防止策**
- **開発効率向上**

## 🎯 責任分離設計実装 (v2.2.0 更新)

### ✅ enabled 管理責任分離
```
AIChat の責任:
- ユーザーの enabled 設定管理
- enabled=true のツールのみ呼び出し
- ユーザーインターフェース制御

MCP Server の責任:
- 呼び出されたツールの確実な実行
- 自サーバーのツールかどうかの確認
- 不正なツール名の拒否
- enabled チェックは不要 (AIChat側で制御)
```

### ✅ CRM-MCP enabled フィルタリング削除
```python
# 修正前: 不要な enabled チェック
enabled_tools = [tool for tool in tools_list if tool.get("enabled", False)]

# 修正後: CRM MCP ツール確認のみ
crm_tools = [tool for tool in tools_list if tool.get("mcp_server_name") == "CRM MCP"]
```

### ✅ is_valid_tool の正しい役割
```python
# 正しい責任
1. CRM MCP のツールかどうか確認
2. 不正なツール名のエラーハンドリング  
3. ProductMaster MCP ツール呼び出し拒否

# 削除された不要な責任
❌ enabled 状態チェック (AIChat側に委譲)
```

## 📊 result 構造統一実装 (v2.2.0 更新)

### ✅ MCPResponse result 構造統一
**全MCPツールで統一的なシンプル文字列構造実装**

#### **統一前の問題**
```python
# ProductMaster-MCP (問題のあった構造)
return MCPResponse(
    result={
        "content": [{"type": "text", "text": final_result}],
        "isError": False
    }
)

# CRM-MCP (正しい構造)
return MCPResponse(
    result=formatted_response  # シンプルな文字列
)
```

#### **統一後の構造**
```python
# 全MCPツールで統一
return MCPResponse(
    result=final_result,  # シンプルな文字列
    debug_response=tool_debug
)
```

### ✅ AIChat integration_engine.py 最適化
```python
# results_summary 作成最適化
results_summary = "\n\n".join([
    f"【Step {step.step}: {step.tool}】\n理由: {step.reason}\n結果: {step.output.get('result', str(step.output)) if isinstance(step.output, dict) else str(step.output)}"
    for step in executed_strategy.steps if step.output
])
```

### ✅ ハルシネーション防止効果
```
修正前: 大量のデバッグ情報 → LLMが混乱
修正後: 簡潔な結果のみ → LLMが正確に理解
```

## 🎯 ProductMaster-MCP 完全リファクタリング (v2.2.0 新規)

### ✅ get_product_details → get_product_details_byid 変更
**ID検索専用ツールとして完全リファクタリング**

#### **変更内容**
```python
# ツール名変更
get_product_details → get_product_details_byid

# 機能変更
複雑なテキスト解析 → シンプルなID配列検索
SystemPrompt多段階処理 → LLM ID抽出 + データベース検索
```

#### **新しい処理フロー**
```python
1. get_product_details_byid()          # メイン関数
2. extract_product_ids_with_llm()      # LLMによるID抽出
3. execute_product_search_query()      # ID配列でデータベース検索
4. format_product_search_results()     # 結果整形
```

### ✅ LLM ID抽出システム実装
**SystemPrompt: get_product_details_byid_extract_ids**

#### **抽出ルール**
```
1. 商品ID、product_id、ID等の文脈で使用されている数字
2. 括弧内の数字（例: (ID: 8)、Microsoft Corporation (ID: 8)）
3. カンマ区切りの数字列（例: 1,2,3）
4. 配列形式の数字（例: [1,2,3]）
5. 単独の数字（文脈から商品IDと推測される場合）

出力形式: [11,2,43] (配列形式文字列)
```

#### **安全なパース処理**
```python
import ast
try:
    product_ids = ast.literal_eval(response.strip())
    if not isinstance(product_ids, list):
        raise ValueError("応答が配列形式ではありません")
    product_ids = list(set([int(id) for id in product_ids if isinstance(id, (int, str)) and str(id).isdigit()]))
except (ValueError, SyntaxError, TypeError) as parse_error:
    # パースエラー情報を詳細に記録・後続処理に渡す
    debug_info["extract_ids_parsed_successfully"] = False
    debug_info["extract_ids_parse_error"] = str(parse_error)
    return []
```

### ✅ パースエラー処理システム
**ハルシネーション対策として完全なエラーハンドリング実装**

#### **エラー情報の後続処理への受け渡し**
```python
# メイン関数でパースエラー検出
if debug_info.get("extract_ids_parsed_successfully") == False:
    error_message = await format_product_search_results([], debug_info)

# フォーマット関数でパースエラー情報処理
if debug_info.get("extract_ids_parsed_successfully") == False:
    parse_error_info = debug_info.get("extract_ids_final_result", "パースエラーが発生しました")
    return f"商品ID抽出でエラーが発生しました: {parse_error_info}、回答は不正なものになる可能性があります。"
```

#### **完全なトレーサビリティ**
```json
{
  "extract_ids_parsed_successfully": false,
  "extract_ids_parse_error": "malformed node or string: line 1",
  "extract_ids_final_result": "パースエラー: malformed node or string (LLM応答: 商品IDは8です)",
  "extract_ids_llm_response": "商品IDは8です"
}
```

### ✅ SystemPrompt命名規則統一
**{ツール名}_{機能名} 形式で統一**

#### **統一後のプロンプト構成**
```
get_product_details_byid関連:
- get_product_details_byid_extract_ids: ID抽出用
- get_product_details_byid_format_result: 結果整形用

search_products_by_name_fuzzy関連:
- fuzzy_search_extract_criteria: 検索条件抽出用
- fuzzy_search_format_results: 結果整形用
```

#### **削除された未使用プロンプト**
```
削除済み（未使用）:
- extract_product_info_pre (161文字)
- extract_product_keywords_pre (278文字)
- format_product_search_results → get_product_details_byid_format_result に変更
```

### ✅ データベースクリーンアップ完了
**get_system_prompt 重複削除・統一的なSystemPrompt取得実現**

#### **修正内容**
```python
# utils/database.py から get_system_prompt 削除 (26行削除)
# tools/product_search.py インポート修正
- from utils.database import get_db_connection, get_system_prompt
+ from utils.database import get_db_connection
+ from utils.system_prompt import get_system_prompt
```

#### **責任分離の明確化**
```
ProductMaster-MCP:
- 商品データ: productmaster DB直接アクセス (utils/database.py)
- システムプロンプト: SystemPrompt Management API経由 (utils/system_prompt.py)
```

## 🔄 移行計画

### ✅ Phase 1: AIChat 統一完了 (完了済み)
- MCPToolManager 実装完了
- class MCPTool 辞書化対応完了
- 全モジュール共有アクセス実装完了
- 防御構文実装完了

### ✅ Phase 2: CRM-MCP 移行完了 (完了済み)
- tools_config.json 廃止完了
- tools_manager.py → MCP-Management API対応完了
- enabled フィルタリング削除完了
- 責任分離実装完了
- 防御構文実装完了

### ✅ Phase 3: ProductMaster-MCP 移行完了 (完了済み)
- result 構造統一完了
- 防御構文実装完了
- get_product_details_byid リファクタリング完了
- LLM ID抽出システム実装完了
- パースエラー処理システム実装完了
- SystemPrompt命名規則統一完了
- データベースクリーンアップ完了

### 📋 Phase 4: 他MCPサーバー移行
- 新規MCPサーバー統一設計適用

## 🎯 現在の状況 (v2.2.0)

### ✅ 完全解決済み問題
```
1. enabled フィルタリング問題 → 責任分離で解決
2. ValidationException 問題 → 防御構文で解決
3. result 構造不統一問題 → 構造統一で解決
4. ハルシネーション問題 → 情報量削減・パースエラー処理で解決
5. 二重管理・データ不整合 → 一元管理で解決
6. get_system_prompt 重複問題 → 統一実装で解決
7. SystemPrompt命名不統一 → 命名規則統一で解決
8. 未使用プロンプト問題 → クリーンアップで解決
```

### ✅ 実装完了機能
```
1. 連続MCPツール実行 → 完全動作
2. 統一的な防御構文 → 全MCPツールで実装
3. 責任分離設計 → AIChat・MCP Server間で実現
4. result 構造統一 → 全MCPツールで統一
5. ハルシネーション防止 → 情報量最適化・エラー処理
6. LLM ID抽出システム → 高精度・安全なID抽出
7. パースエラー処理 → 完全なエラーハンドリング
8. SystemPrompt管理 → 統一命名規則・クリーンアップ
```

## 📊 統一後のメリット

### ✅ 一元管理実現
- 設定変更: MCP-Management のみ
- ツール追加: データベース登録のみ
- 名前統一: tool_key で完全一致

### ✅ 開発効率向上
- 設定ファイル重複管理解消
- デバッグ情報統一
- 型安全性向上
- ValidationException 根本的防止
- SystemPrompt管理効率化

### ✅ 運用安定性向上
- データ不整合解消
- 設定変更の影響範囲明確化
- 障害時の原因特定容易化
- ハルシネーション大幅削減
- パースエラー安全処理

### ✅ 保守性向上
- コードの可読性向上（関数順序統一）
- SystemPrompt命名規則統一
- 未使用リソース削除
- 責任分離明確化

## 🔧 実装ガイドライン

### ✅ 新規MCPサーバー作成時
1. MCP-Management でツール登録
2. MCPToolManager.initialize() で読み込み確認
3. 独自設定ファイル作成禁止
4. llm_util.py に防御構文実装
5. result はシンプルな文字列で返却
6. SystemPrompt命名規則: {ツール名}_{機能名}
7. 関数順序: メイン関数先頭・呼び出し順配置

### ✅ 既存MCPサーバー修正時
1. 独自設定ファイル削除
2. MCP-Management API対応実装
3. ツール名統一確認
4. enabled フィルタリング削除
5. 防御構文追加
6. result 構造統一
7. SystemPrompt命名規則統一
8. 未使用リソース削除

### ✅ デバッグ時
1. MCP-Management データベース確認
2. MCPToolManager.registered_tools 辞書確認
3. 実際のMCPサーバー稼働確認
4. 防御構文動作確認
5. result 構造確認
6. パースエラー処理確認

## 🌐 アクセス情報

### ✅ 統合システム
- **Portal**: http://44.217.45.24/
- **AIChat**: http://44.217.45.24/aichat/
- **MCP-Management**: http://44.217.45.24:8008/

### ✅ 動作確認
- **連続MCPツール実行**: 「AAPLを保有する顧客を教えて」
- **結果**: search_products_by_name_fuzzy → get_customers_by_product_text
- **表示**: 簡潔で正確な結果のみ表示
- **ID検索**: 「Microsoft Corporation (ID: 8)の詳細を教えて」
- **結果**: get_product_details_byid でID抽出・商品詳細取得

---

**MCP統一アーキテクチャ v2.2.0 - ProductMaster-MCP完全リファクタリング・LLM ID抽出・パースエラー処理・SystemPrompt統一管理による完全統合設計**

**実装完了日**: 2025-09-22
**主要改善**: ID検索専用化・LLM抽出システム・ハルシネーション対策・SystemPrompt統一管理・データベースクリーンアップ
