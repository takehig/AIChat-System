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
        
        # フォールバック用デフォルトプロンプト
        self.fallback_prompts = {
            "strategy_planning": """あなたは戦略立案の専門家です。ユーザーリクエストを分析し、必要最小限のツールのみを選択してください。

## 重要な判定ルール
1. ユーザーが明示的に要求していない情報は取得しない
2. 利用可能ツールの中から適切なものを選択する
3. ツールが不要な場合は steps を空配列 [] にする
4. 複数ツールの無駄な組み合わせを避ける

## 判定の考え方
- 情報要求の種類を特定する（商品情報、顧客情報、その他）
- 利用可能ツールの説明文と照らし合わせる
- 明示的に要求されていない情報は取得しない
- 一般的な挨拶や質問にはツールは不要"""
        }
    
    def get_prompt(self, prompt_key: str) -> str:
        """
        SystemPrompt Management からプロンプトを取得
        
        Args:
            prompt_key: プロンプトキー（例: "strategy_planning"）
            
        Returns:
            str: プロンプト文字列
        """
        try:
            # SystemPrompt Management API呼び出し
            url = f"{self.base_url}/api/prompt/{prompt_key}"
            logger.info(f"[SystemPrompt] API呼び出し: {url}")
            
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            prompt_text = data.get("prompt_text", "")
            
            if prompt_text:
                logger.info(f"[SystemPrompt] プロンプト取得成功: {prompt_key}")
                return prompt_text
            else:
                logger.warning(f"[SystemPrompt] プロンプトが空: {prompt_key}")
                return self._get_fallback_prompt(prompt_key)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"[SystemPrompt] API接続エラー: {e}")
            return self._get_fallback_prompt(prompt_key)
        except Exception as e:
            logger.error(f"[SystemPrompt] 予期しないエラー: {e}")
            return self._get_fallback_prompt(prompt_key)
    
    def _get_fallback_prompt(self, prompt_key: str) -> str:
        """
        フォールバックプロンプトを取得
        
        Args:
            prompt_key: プロンプトキー
            
        Returns:
            str: フォールバックプロンプト
        """
        fallback = self.fallback_prompts.get(prompt_key, "")
        if fallback:
            logger.info(f"[SystemPrompt] フォールバック使用: {prompt_key}")
            return fallback
        else:
            logger.error(f"[SystemPrompt] フォールバックも見つからない: {prompt_key}")
            return "あなたは親切なAIアシスタントです。ユーザーの質問に丁寧に回答してください。"
    
    def health_check(self) -> bool:
        """
        SystemPrompt Management の稼働状況確認
        
        Returns:
            bool: 稼働中の場合True
        """
        try:
            url = f"{self.base_url}/api/status"
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            status = data.get("status", "")
            
            if status == "running":
                logger.info("[SystemPrompt] ヘルスチェック成功")
                return True
            else:
                logger.warning(f"[SystemPrompt] サービス状態異常: {status}")
                return False
                
        except Exception as e:
            logger.error(f"[SystemPrompt] ヘルスチェック失敗: {e}")
            return False
