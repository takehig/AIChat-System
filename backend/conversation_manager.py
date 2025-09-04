import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, storage_path: str = "/tmp/aichat_conversations.json"):
        self.storage_path = storage_path
        self.conversations = self.load_conversations()
    
    def load_conversations(self) -> Dict[str, List[Dict]]:
        """会話履歴をファイルから読み込み"""
        try:
            if os.path.exists(self.storage_path):
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load conversations: {e}")
        return {}
    
    def save_conversations(self):
        """会話履歴をファイルに保存"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save conversations: {e}")
    
    def get_session_id(self, request_data: Dict) -> str:
        """セッションIDを生成（IPアドレス + 日付ベース）"""
        # 簡易的なセッション識別
        today = datetime.now().strftime("%Y-%m-%d")
        return f"session_{today}"
    
    def add_message(self, session_id: str, user_message: str, ai_response: str, strategy_info: Dict = None):
        """会話履歴に追加"""
        if session_id not in self.conversations:
            self.conversations[session_id] = []
        
        conversation_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": user_message,
            "ai_response": ai_response,
            "strategy_info": strategy_info or {}
        }
        
        self.conversations[session_id].append(conversation_entry)
        
        # 最新20件のみ保持
        if len(self.conversations[session_id]) > 20:
            self.conversations[session_id] = self.conversations[session_id][-20:]
        
        self.save_conversations()
    
    def get_conversation_context(self, session_id: str, max_messages: int = 5) -> str:
        """会話コンテキストを取得"""
        if session_id not in self.conversations:
            return ""
        
        recent_messages = self.conversations[session_id][-max_messages:]
        
        context_parts = []
        for msg in recent_messages:
            context_parts.append(f"ユーザー: {msg['user_message']}")
            context_parts.append(f"AI: {msg['ai_response']}")
        
        if context_parts:
            return "## 前回までの会話履歴\n" + "\n".join(context_parts) + "\n\n"
        
        return ""
    
    def clear_session(self, session_id: str):
        """特定セッションの履歴をクリア"""
        if session_id in self.conversations:
            del self.conversations[session_id]
            self.save_conversations()
