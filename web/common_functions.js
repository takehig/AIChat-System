// 共通関数
async function clearChat() {
    // フロントエンドのチャット表示クリア
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="message ai">
            <div><strong>Claude 3.7 Sonnet</strong></div>
            <div>こんにちは！何でもお気軽にお聞きください。</div>
            <div class="message-time">システム起動時</div>
        </div>
    `;
    
    // バックエンドの会話履歴もクリア
    try {
        const response = await fetch('/aichat/api/clear-conversation', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                conversation_id: 'default',
                message: ''
            })
        });
        
        if (response.ok) {
            console.log('[CLEAR] 会話履歴をクリアしました');
        } else {
            console.error('[CLEAR] 会話履歴クリア失敗:', response.status);
        }
    } catch (error) {
        console.error('[CLEAR] 会話履歴クリアエラー:', error);
    }
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('messageInput').focus();
    initializeProductMasterMCP();
});
