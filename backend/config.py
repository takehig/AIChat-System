# AIChat Backend Configuration

# AIChat専用データベース設定（システムプロンプト管理）
AICHAT_DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "aichat",
    "user": "aichat_user",
    "password": "aichat123"
}

# Bedrock設定
BEDROCK_CONFIG = {
    "region_name": "us-east-1",
    "model_id": "anthropic.claude-3-sonnet-20240229-v1:0"
}

# サーバー設定
SERVER_CONFIG = {
    "title": "AIChat Backend",
    "version": "2.0.0",
    "port": 8002
}
