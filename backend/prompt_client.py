# SystemPrompt Management API クライアント
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class SystemPromptClient:
    """SystemPrompt Management API クライアント"""
    
    def __init__(self, base_url: str = "http://localhost:8007"):
        self.base_url = base_url
        self.timeout = 5  # 5秒タイムアウト
    
    def get_prompt(self, prompt_key: str) -> str:
        """
        SystemPrompt Management からプロンプトを取得
        
        Args:
            prompt_key: プロンプトキー（例: "strategy_planning"）
            
        Returns:
            str: プロンプト文字列
            
        Raises:
            Exception: API接続エラーまたはプロンプト取得失敗時
        """
        # SystemPrompt Management API呼び出し
        url = f"{self.base_url}/api/prompt/{prompt_key}"
        logger.info(f"[SystemPrompt] API呼び出し: {url}")
        
        response = requests.get(url, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        prompt_text = data.get("prompt_text", "")
        
        if not prompt_text:
            raise Exception(f"プロンプトが空: {prompt_key}")
        
        logger.info(f"[SystemPrompt] プロンプト取得成功: {prompt_key}")
        return prompt_text
    
    def health_check(self) -> bool:
        """
        SystemPrompt Management の稼働状況確認
        
        Returns:
            bool: 稼働中の場合True
        """
        try:
            url = f"{self.base_url}/api/status"
            response = requests.get(url, timeout=self.timeout)
            return response.status_code == 200
        except:
            return False

# グローバルインスタンス
prompt_client = SystemPromptClient()
