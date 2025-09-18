# AIChat System v2.1.0

## 概要
WealthAI Enterprise Systems用AI対話システム - MCP統合・戦略エンジン・エラーハンドリング完備

## 🎯 主要機能
- **AI対話**: Amazon Bedrock Claude 3 Sonnet統合
- **MCP統合**: Model Context Protocol対応・拡張可能アーキテクチャ
- **戦略エンジン**: 自動戦略立案・実行・応答生成
- **エラーハンドリング**: 完全参照渡し設計・デバッグ情報保持
- **MCPツールアイコン管理**: 確定的アイコン表示・拡張対応

## 🏗️ 技術スタック
- **Backend**: Python FastAPI + asyncio
- **Frontend**: HTML5 + Bootstrap 5 + JavaScript ES6+
- **AI**: Amazon Bedrock Claude 3 Sonnet
- **Protocol**: Model Context Protocol (MCP)
- **Port**: 8002

## 🔧 MCPツールアイコン管理システム v2.1.0

### ✅ 確定的アイコン表示機能
**ツール名→システム種別→アイコンの確定的マッピング実装**

#### **グローバル辞書設定**
```python
# backend/mcp_manager.py
MCP_TOOL_SYSTEM_MAP = {
    # ProductMaster MCP ツール
    'get_product_details': 'productmaster',
    
    # CRM MCP ツール
    'search_customers_by_bond_maturity': 'crm',
    'get_customer_holdings': 'crm',
    
    # 将来追加用
    # 'get_market_data': 'market_data',
}

MCP_SYSTEM_ICONS = {
    'productmaster': 'fa-box',      # 📦 商品管理
    'crm': 'fa-users',              # 👥 顧客管理
    'market_data': 'fa-chart-line', # 📈 市場データ (将来用)
    'default': 'fa-tool'            # 🔧 デフォルト
}
```

#### **JavaScript側同期実装**
```javascript
// web/index.html
const MCP_TOOL_SYSTEM_MAP = { /* Python側と同じ */ };
const MCP_SYSTEM_ICONS = { /* Python側と同じ */ };

function getToolIcon(toolName) {
    const systemType = MCP_TOOL_SYSTEM_MAP[toolName] || 'default';
    return MCP_SYSTEM_ICONS[systemType] || MCP_SYSTEM_ICONS['default'];
}
```

#### **現在のアイコンマッピング**
- **商品詳細情報を取得** (`get_product_details`) → 📦 `fa-box`
- **債券の満期日条件で顧客を検索** (`search_customers_by_bond_maturity`) → 👥 `fa-users`
- **顧客の保有商品情報を取得** (`get_customer_holdings`) → 👥 `fa-users`

### ✅ 新MCPツール追加手順
1. **辞書登録**: `MCP_TOOL_SYSTEM_MAP` にツール名追加
2. **システム種別追加**: 必要に応じて `MCP_SYSTEM_ICONS` に新種別追加
3. **両側同期**: Python・JavaScript両方に同じ設定を追加

## 🎯 エラーハンドリング v2.0.0 完全参照渡し設計

### ✅ 段階的情報保持
```python
# 完全参照渡し設計
executed_strategy = DetailedStrategy(steps=[])  # Try外で初期化
try:
    await plan_strategy(user_message, executed_strategy)           # 戦略情報追加
    await execute_detailed_strategy(executed_strategy, user_message)  # 実行結果追加
    await generate_final_response(user_message, executed_strategy)    # 応答情報追加
except Exception as e:
    return {"strategy": executed_strategy, "error": str(e)}  # 途中情報完全保持
```

### ✅ エラー時情報保持
- **戦略立案情報**: strategy_llm_prompt, strategy_llm_response
- **実行結果**: steps[].input, output, execution_time_ms, debug_info
- **MCP呼び出し結果**: 完全なデバッグ情報
- **部分応答**: エラー発生時も部分的な応答保持

## 🔗 MCP統合アーキテクチャ

### 対応MCPサーバー
```python
self.available_mcps = {
    'productmaster': {
        'name': 'ProductMaster',
        'description': '商品情報検索MCP',
        'url': 'http://localhost:8003',
        'enabled': False
    },
    'crm': {
        'name': 'CRM',
        'description': '顧客管理システムとの連携機能',
        'url': 'http://localhost:8004',
        'enabled': False
    }
}
```

### MCP拡張パターン
```python
# 新しいMCP追加例
'market_data': {
    'name': 'MarketData',
    'description': '市場データ取得MCP',
    'url': 'http://localhost:8005',
    'enabled': False
}
```

## 🎨 UI機能

### MCPツール管理画面
- **ツール一覧**: 有効化・無効化切り替え
- **アイコン表示**: システム種別別の確定的アイコン
- **テスト実行**: 個別ツールテスト機能
- **デバッグ情報**: コンソールログでマッピング確認

### チャット機能
- **AI対話**: 自然言語での質問・回答
- **MCP統合**: 自動ツール選択・実行
- **戦略表示**: 実行戦略・デバッグ情報表示
- **エラー表示**: 詳細なエラー情報・途中結果表示

## 📊 システム構成

### ファイル構造
```
AIChat/
├── backend/
│   ├── main.py              # FastAPI メインアプリケーション
│   ├── mcp_manager.py       # MCP管理・アイコン辞書
│   ├── ai_agent.py          # AI エージェント・参照渡し設計
│   ├── strategy_engine.py   # 戦略立案エンジン
│   ├── integration_engine.py # 統合・応答生成エンジン
│   └── models.py            # データモデル
└── web/
    └── index.html           # フロントエンド・アイコン管理
```

### API エンドポイント
```
GET  /                       # メインページ
POST /api/chat               # AI対話
GET  /api/mcp/status         # MCP状態取得
POST /api/mcp/toggle         # MCP有効化切り替え
GET  /api/mcp/tools          # MCPツール一覧
POST /api/mcp/test           # MCPツールテスト
```

## 🔍 デバッグ機能

### コンソールログ
```javascript
[MCP DEBUG] getToolIcon called with: get_product_details
[MCP DEBUG] toolName: get_product_details systemType: productmaster icon: fa-box
```

### エラー時デバッグ情報
- **戦略立案**: LLMプロンプト・レスポンス
- **ツール実行**: 入力・出力・実行時間
- **MCP通信**: リクエスト・レスポンス詳細
- **エラー詳細**: スタックトレース・原因情報

## 🚀 アクセス情報
- **URL**: http://44.217.45.24/aichat/
- **直接**: http://44.217.45.24:8002/
- **GitHub**: https://github.com/takehig/AIChat-System

## 🛠️ 開発・運用

### ローカル開発
```bash
# 依存関係インストール
cd backend && pip install -r requirements.txt

# 開発サーバー起動
python main.py
```

### デプロイ手順
```bash
# 1. ローカル修正
git add . && git commit -m "[UPDATE] 機能追加"

# 2. GitHub反映
git push origin main

# 3. EC2反映
# SSM経由でgit pull → サービス再起動
```

### systemd管理
```bash
# サービス管理
sudo systemctl start|stop|restart aichat
sudo systemctl status aichat

# ログ確認
sudo journalctl -u aichat -f
```

## 📈 バージョン履歴

### v2.1.0 (2025-09-19)
- ✅ MCPツールアイコン管理システム実装
- ✅ 確定的アイコン表示・グローバル辞書管理
- ✅ デバッグ機能・コンソールログ追加
- ✅ 新MCPツール追加手順確立

### v2.0.0 (2025-09-16〜17)
- ✅ エラーハンドリング完全参照渡し設計実装
- ✅ 段階的情報保持・デバッグ性向上
- ✅ 設計一貫性・単一オブジェクト管理

### v1.0.0 (2025-08-30)
- ✅ AI対話・MCP統合基本機能実装
- ✅ 戦略エンジン・自動ツール選択
- ✅ FastAPI + Bootstrap 5 UI

## 🔒 セキュリティ
- AWS IAM Role認証
- MCP通信HTTPS対応
- エラー情報適切なマスキング
- デバッグ情報本番環境制御

## 🎯 今後の拡張予定
- [ ] 新MCPサーバー追加（MarketData・News等）
- [ ] チャット履歴保存・検索機能
- [ ] ユーザー別設定・カスタマイズ
- [ ] パフォーマンス監視・メトリクス
