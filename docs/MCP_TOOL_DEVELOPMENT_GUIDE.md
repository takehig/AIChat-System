# MCP ツール開発標準ガイド v1.1.0

## 📋 概要
WealthAI Enterprise Systems における MCP ツール開発の標準化ガイド  
`bond_maturity.py` を基準とした統一的な開発手法・コード構造・LLM統合パターン

## 🚨 MCPResponse標準仕様（最重要）

### ✅ 必須MCPResponse構造
```python
# models.py - 全MCPサーバーで統一すべき構造
class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[int] = None
    result: Any = None                              # メイン結果データ
    error: Optional[str] = None                     # エラーメッセージ
    debug_response: Optional[Dict[str, Any]] = None # デバッグ情報（スキーマレス）
```

### ✅ 正しい使用例
```python
# ✅ 正しい実装 - 必ずこの形式を使用
return MCPResponse(
    result={
        "content": [{"type": "text", "text": "結果テキスト"}],
        "isError": False
    },
    debug_response=tool_debug  # ← 正しいフィールド名
)

# エラー時
return MCPResponse(
    result={
        "content": [{"type": "text", "text": "エラーメッセージ"}],
        "isError": True
    },
    error="エラー詳細",
    debug_response=tool_debug  # ← エラー時も必須
)
```

### ❌ 絶対禁止の間違った実装
```python
# ❌ 間違い - 存在しないフィールド使用禁止
return MCPResponse(
    content=[...],           # ← 存在しない
    isError=False,           # ← 存在しない
    _meta={"debug_info": ...} # ← 存在しない（推測実装禁止）
)
```

### 🎯 debug_response設計原則

#### **スキーマレス設計の重要性**
- **柔軟性**: ツール毎に異なるデバッグ情報構造を許可
- **拡張性**: 新しいデバッグ情報を自由に追加可能
- **統一性**: 基本的なフィールドは統一、詳細は自由

#### **推奨デバッグ情報構造**
```python
# 標準的なdebug_response構造
debug_response = {
    "function_name": "tool_function_name",     # 必須
    "input_params": {...},                    # 必須
    "step1_xxx": {                            # 処理段階毎（自由構造）
        "llm_request": "結合済み文字列",        # LLMリクエスト全体
        "llm_response": "...",                # LLMレスポンス
        "execution_time_ms": 123,             # 実行時間
        "result": {...}                       # 段階結果
    },
    "step2_xxx": {...},                       # 段階毎に自由に追加
    "api_calls": [...],                       # API呼び出し情報
    "database_queries": [...],                # DB クエリ情報
    "total_execution_time_ms": 1234,          # 総実行時間（推奨）
    "error": None                             # エラー情報（推奨）
}
```

#### **LLMリクエスト記録の重要性**
```python
# ✅ 正しいLLMリクエスト記録
full_prompt = f"{system_prompt}\n\nUser Input: {user_input}"
tool_debug["step1_llm_request"] = full_prompt  # ← 結合済み文字列

response, execution_time = await llm_util.call_llm_simple(full_prompt)
tool_debug["step1_llm_response"] = response
tool_debug["step1_execution_time_ms"] = execution_time

# ❌ 間違い - 分離した記録
tool_debug["system_prompt"] = system_prompt    # ← 分離記録禁止
tool_debug["user_message"] = user_input        # ← 分離記録禁止
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

## 🏗️ 標準アーキテクチャ

### 🎯 3段階処理パターン
```python
async def main_tool_function(params: Dict[str, Any]) -> MCPResponse:
    """メインツール関数 - 3段階処理の統合"""
    start_time = time.time()
    
    # Try外でdebug_response初期化（エラー時情報保持）
    tool_debug = {
        "function_name": "main_tool_function",
        "input_params": params,
        "step1_standardize": {...},
        "step2_business_logic": {...},
        "step3_format": {...},
        "total_execution_time_ms": 0,
        "error": None
    }
    
    try:
        # 1. 引数標準化処理（LLMベース）
        standardized_params = await standardize_arguments(raw_input, tool_debug)
        
        # 2. データベース処理・ビジネスロジック実行
        results = await execute_business_logic(standardized_params, tool_debug)
        
        # 3. 結果フォーマット処理（LLMベース）
        formatted_result = await format_results(results, user_input, tool_debug)
        
        # 実行時間記録
        tool_debug["total_execution_time_ms"] = int((time.time() - start_time) * 1000)
        
        return MCPResponse(
            result=formatted_result, 
            debug_response=tool_debug  # ← 必須
        )
        
    except Exception as e:
        # エラー時もdebug_response保持
        tool_debug["error"] = str(e)
        tool_debug["total_execution_time_ms"] = int((time.time() - start_time) * 1000)
        
        return MCPResponse(
            result={"content": [{"type": "text", "text": f"エラー: {str(e)}"}], "isError": True},
            error=str(e),
            debug_response=tool_debug  # ← エラー時も必須
        )
```

## 🔧 実装標準パターン

### ✅ 1. メインツール関数構造

#### **基本テンプレート**
```python
import time
import json
from typing import Dict, Any, Tuple, List
from utils.database import get_db_connection
from utils.system_prompt import get_system_prompt
from utils.llm_util import llm_util
from models import MCPResponse
from psycopg2.extras import RealDictCursor

async def your_tool_function(params: Dict[str, Any]) -> MCPResponse:
    """ツール説明"""
    start_time = time.time()
    
    print(f"[your_tool_function] === FUNCTION START ===")
    print(f"[your_tool_function] Received raw params: {params}")
    
    # Try外で初期化（エラー時情報保持）
    tool_debug = {
        "function_name": "your_tool_function",
        "input_params": params,
        "step1_standardize": {
            "llm_request": None,
            "llm_response": None,
            "execution_time_ms": 0
        },
        "step2_database": {
            "query": None,
            "results_count": 0
        },
        "step3_format": {
            "llm_request": None,
            "llm_response": None,
            "execution_time_ms": 0
        },
        "total_execution_time_ms": 0,
        "error": None
    }
    
    try:
        # 処理実装...
        
        return MCPResponse(
            result=final_result,
            debug_response=tool_debug
        )
        
    except Exception as e:
        tool_debug["error"] = str(e)
        tool_debug["total_execution_time_ms"] = int((time.time() - start_time) * 1000)
        
        return MCPResponse(
            result={"content": [{"type": "text", "text": f"エラー: {str(e)}"}], "isError": True},
            error=str(e),
            debug_response=tool_debug
        )
```
        "standardize_prompt": None,
        "standardize_response": None,
        "standardize_parameter": None,
        "executed_query": None,
        "executed_query_results": None,
        "format_response": None,
        "execution_time_ms": None,
        "results_count": None
    }
    
    try:
        # 1. 引数標準化処理（参照渡し）
        standardized_params = await standardize_your_tool_arguments(str(params), tool_debug)
        
        # 2. ビジネスロジック実行（参照渡し）
        results = await execute_your_tool_logic(standardized_params, tool_debug)
        
        # 3. 結果フォーマット処理（参照渡し）
        result_text = await format_your_tool_results(results, str(params), tool_debug)
        
        execution_time = time.time() - start_time
        tool_debug["execution_time_ms"] = round(execution_time * 1000, 2)
        tool_debug["results_count"] = len(results) if isinstance(results, list) else 1
        
        print(f"[your_tool_function] === FUNCTION END ===")
        return MCPResponse(result=result_text, debug_response=tool_debug)
        
    except Exception as e:
        execution_time = time.time() - start_time
        error_message = f"ツール実行エラー: {str(e)}"
        
        tool_debug["execution_time_ms"] = round(execution_time * 1000, 2)
        tool_debug["results_count"] = 0
        
        print(f"[your_tool_function] ERROR: {error_message}")
        return MCPResponse(result=error_message, debug_response=tool_debug, error=str(e))
```

#### **重要な設計原則**
1. **完全参照渡し設計**: `tool_debug` を全関数で参照渡し
2. **Try外初期化**: エラー時も途中情報を保持
3. **詳細ログ出力**: 各段階でデバッグ情報出力
4. **実行時間計測**: パフォーマンス監視
5. **統一エラーハンドリング**: MCPResponse形式で統一

### ✅ 2. 引数標準化処理（第1段階）

#### **LLMベース引数標準化**
```python
async def standardize_your_tool_arguments(raw_input: str, tool_debug: Dict) -> Dict[str, Any]:
    """引数標準化処理 - LLMで自然言語→構造化データ"""
    print(f"[standardize_your_tool_arguments] Raw input: {raw_input}")
    
    # システムプロンプト取得
    system_prompt = await get_system_prompt("your_tool_name_pre")
    
    print(f"[standardize_your_tool_arguments] === LLM CALL START ===")
    response = await llm_util.call_claude(system_prompt, raw_input)
    print(f"[standardize_your_tool_arguments] LLM Raw Response: {response}")
    print(f"[standardize_your_tool_arguments] === LLM CALL END ===")
    
    full_prompt_text = f"{system_prompt}\n\nUser Input: {raw_input}"
    
    # tool_debugに情報設定（参照渡し）
    tool_debug["standardize_prompt"] = full_prompt_text
    tool_debug["standardize_response"] = response
    
    try:
        standardized_params = json.loads(response)
        print(f"[standardize_your_tool_arguments] Final Standardized Output: {standardized_params}")
        tool_debug["standardize_parameter"] = str(standardized_params)
        return standardized_params
    except json.JSONDecodeError as e:
        print(f"[standardize_your_tool_arguments] JSON parse error: {e}")
        tool_debug["standardize_parameter"] = f"JSONパースエラー: {str(e)}"
        return {}
```

#### **システムプロンプト命名規則**
- **前処理**: `{tool_name}_pre` (例: `search_customers_by_bond_maturity_pre`)
- **後処理**: `{tool_name}_post` (例: `search_customers_by_bond_maturity_post`)

### ✅ 3. ビジネスロジック実行（第2段階）

#### **データベース処理標準パターン**
```python
async def execute_your_tool_logic(standardized_params: Dict, tool_debug: Dict) -> List[Dict]:
    """ビジネスロジック実行 - データベース処理・計算処理"""
    
    # パラメータ抽出
    param1 = standardized_params.get("param1")
    param2 = standardized_params.get("param2")
    
    print(f"[execute_your_tool_logic] Extracted values:")
    print(f"  - param1: {param1}")
    print(f"  - param2: {param2}")
    
    # データベース接続
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    # クエリ構築
    query = """
    SELECT column1, column2, column3
    FROM table1 t1
    JOIN table2 t2 ON t1.id = t2.foreign_id
    WHERE condition = %s
    """
    query_params = [param1]
    
    # 動的条件追加
    if param2:
        query += " AND additional_condition = %s"
        query_params.append(param2)
    
    query += " ORDER BY column1 ASC"
    
    print(f"[execute_your_tool_logic] Final query: {query}")
    print(f"[execute_your_tool_logic] Query params: {query_params}")
    
    # tool_debugにクエリ情報設定
    tool_debug["executed_query"] = query
    
    # SQL実行
    if query_params:
        cursor.execute(query, query_params)
    else:
        cursor.execute(query)
    
    results = cursor.fetchall()
    conn.close()
    
    print(f"[execute_your_tool_logic] Query executed, found {len(results)} rows")
    
    # 結果配列作成
    processed_results = []
    for row in results:
        processed_results.append({
            "field1": row['column1'],
            "field2": row['column2'],
            "field3": row['column3'],
            # 必要に応じて計算・変換処理
        })
    
    # tool_debugに結果設定
    tool_debug["executed_query_results"] = processed_results
    
    return processed_results
```

#### **データベース処理のベストプラクティス**
1. **RealDictCursor使用**: 辞書形式でのデータアクセス
2. **パラメータ化クエリ**: SQLインジェクション対策
3. **動的クエリ構築**: 条件に応じたクエリ組み立て
4. **接続管理**: 適切な接続クローズ
5. **デバッグ情報保存**: クエリ・結果をtool_debugに保存

### ✅ 4. 結果フォーマット処理（第3段階）

#### **LLMベース結果フォーマット**
```python
async def format_your_tool_results(results: list, user_input: str, tool_debug: Dict) -> str:
    """結果フォーマット処理 - 構造化データ→自然言語"""
    
    if not results:
        return "検索結果: 該当するデータはありませんでした。"
    
    # システムプロンプト取得
    system_prompt = await get_system_prompt("your_tool_name_post")
    
    # データJSON化
    data_json = json.dumps(results, ensure_ascii=False, default=str, indent=2)
    full_prompt = f"{system_prompt}\n\nData:\n{data_json}"
    
    # tool_debugにformat_request設定
    tool_debug["format_request"] = full_prompt
    
    # LLM呼び出し
    result_text, execution_time = await llm_util.call_llm_simple(full_prompt)
    print(f"[format_your_tool_results] Execution time: {execution_time}ms")
    print(f"[format_your_tool_results] Formatted result: {result_text[:200]}...")
    
    # tool_debugにformat_response設定
    tool_debug["format_response"] = result_text
    
    return result_text
```

## 🎯 システムプロンプト設計

### ✅ 前処理プロンプト（_pre）

#### **引数標準化プロンプトテンプレート**
```
あなたは、{ツール名}の引数作成エージェントです。
入力は不定形で、{システム説明}に対しての指示に対する処理の中間データとしてのテキストを受け取ります。

この入力は{処理内容}が必要だと判断したAI Agentの戦略によって、{具体的な処理内容}を行う為の{必要パラメータ}情報が含まれています。

後続の処理は{後続処理説明}を実行します。その為の標準形式を作成する必要があります。

標準形式はJSON形式で以下のような形式のアウトプットです。
{
  "param1": "値1",
  "param2": "値2",
  "param3": 数値
}

例:
入力: "{入力例}" → 出力：{"出力例"}

与えられたテキストから、{抽出対象}を判断し、{処理対象}を抽出してください。
どんな形式の入力でも強引に標準形式に変換してください。ただし、{抽出失敗時の処理}。
必ずJSON形式のみで回答してください。
```

### ✅ 後処理プロンプト（_post）

#### **結果フォーマットプロンプトテンプレート**
```
あなたは、{ツール名}の検索結果を、後続のツールやテキストの整形用のLLM問い合わせが使いやすいように非正規テキスト化するエージェントです。

入力は以下のサンプルのような元の問い合わせとなるプロンプトとJSON形式の結果が結合されたテキストを受け取ります。

{サンプル入力例}

このテキストを後続のツールが使いやすいようなテキストに変換してください。

例：
{フォーマット例}

この後に実際の元の問い合わせとなるプロンプトとクエリ結果が結合されたテキストが続きます。例に沿って加工してください。
```

## 🔧 LLM統合パターン

### ✅ LLMユーティリティ使用方法

#### **基本的なLLM呼び出し**
```python
from utils.llm_util import llm_util

# Claude呼び出し（システムプロンプト + ユーザー入力）
response = await llm_util.call_claude(system_prompt, user_input)

# シンプルLLM呼び出し（完全プロンプト）
result_text, execution_time = await llm_util.call_llm_simple(full_prompt)
```

#### **システムプロンプト取得**
```python
from utils.system_prompt import get_system_prompt

# データベースからシステムプロンプト取得
system_prompt = await get_system_prompt("prompt_key")
```

## 📊 デバッグ情報標準化

### ✅ tool_debug構造

#### **標準デバッグ情報フィールド**
```python
tool_debug = {
    # 第1段階: 引数標準化
    "standardize_prompt": "完全なLLMプロンプト",
    "standardize_response": "LLMの生レスポンス", 
    "standardize_parameter": "標準化されたパラメータ",
    
    # 第2段階: ビジネスロジック
    "executed_query": "実行されたSQLクエリ",
    "executed_query_results": "クエリ実行結果",
    
    # 第3段階: 結果フォーマット
    "format_request": "フォーマット用完全プロンプト",
    "format_response": "フォーマット済み結果",
    
    # 全体情報
    "execution_time_ms": "実行時間（ミリ秒）",
    "results_count": "結果件数"
}
```

## 🗂️ ファイル構成標準

### ✅ MCPプロジェクト構造
```
MCP-Project/
├── main.py                 # FastAPI メインアプリケーション
├── models.py               # MCPResponse等のデータモデル
├── tools_config.json       # ツール設定
├── tools_manager.py        # ツール管理
├── config.py               # 設定管理
├── requirements.txt        # 依存関係
├── tools/                  # ツール実装
│   ├── __init__.py
│   ├── your_tool.py        # 個別ツール実装
│   └── another_tool.py
└── utils/                  # ユーティリティ
    ├── __init__.py
    ├── database.py         # データベース接続
    ├── system_prompt.py    # システムプロンプト取得
    └── llm_util.py         # LLM呼び出し
```

### ✅ ツールファイル命名規則
- **ファイル名**: `{機能名}.py` (例: `bond_maturity.py`)
- **関数名**: `{動詞}_{対象}_{条件}` (例: `search_customers_by_bond_maturity`)
- **プロンプトキー**: `{関数名}_pre` / `{関数名}_post`

## 🚀 開発手順

### ✅ 新MCPツール開発ステップ

#### **Step 1: 要件定義**
1. ツールの目的・機能を明確化
2. 入力パラメータ・出力形式を定義
3. 必要なデータベーステーブル・カラムを特定

#### **Step 2: システムプロンプト作成**
1. SystemPrompt Management で `{tool_name}_pre` プロンプト作成
2. SystemPrompt Management で `{tool_name}_post` プロンプト作成
3. プロンプトのテスト・調整

#### **Step 3: ツール実装**
1. `tools/{tool_name}.py` ファイル作成
2. 3段階処理パターンで実装
3. デバッグ情報・ログ出力の実装

#### **Step 4: 設定・統合**
1. `tools_config.json` にツール追加
2. MCPマネージャーに登録
3. AIChat側のアイコン辞書に追加

#### **Step 5: テスト・デバッグ**
1. 単体テスト実行
2. AIChat統合テスト
3. デバッグ情報確認・調整

## 🔍 トラブルシューティング

### ✅ よくある問題と対処法

#### **LLM呼び出しエラー**
- **症状**: LLM応答がJSON形式でない
- **対処**: システムプロンプトに「必ずJSON形式で回答」を明記
- **デバッグ**: `tool_debug["standardize_response"]` で生レスポンス確認

#### **データベース接続エラー**
- **症状**: データベース接続失敗
- **対処**: `utils/database.py` の接続設定確認
- **デバッグ**: 接続パラメータ・権限確認

#### **システムプロンプト取得エラー**
- **症状**: プロンプトが取得できない
- **対処**: SystemPrompt Management でプロンプトキー確認
- **デバッグ**: プロンプトキーの存在・内容確認

## 📚 参考実装

### ✅ bond_maturity.py 実装例
- **ファイル**: `/home/ec2-user/CRM-MCP/tools/bond_maturity.py`
- **機能**: 債券満期日条件での顧客検索
- **特徴**: 3段階処理・完全参照渡し・詳細デバッグ情報

### ✅ 関連システム
- **SystemPrompt Management**: http://44.217.45.24:8007/
- **AIChat System**: http://44.217.45.24/aichat/
- **Database Management**: http://44.217.45.24/database/

## 📝 更新履歴

### v1.0.0 (2025-09-19)
- ✅ bond_maturity.py ベース標準パターン策定
- ✅ 3段階処理パターン標準化
- ✅ LLM統合・システムプロンプト設計指針
- ✅ デバッグ情報・エラーハンドリング標準化

---

**MCP ツール開発標準ガイド v1.0.0 - WealthAI Enterprise Systems統一開発手法**
