// 共通関数
function clearChat() {
    const chatContainer = document.getElementById('chatContainer');
    chatContainer.innerHTML = `
        <div class="message ai">
            <div><strong>Claude 3.7 Sonnet</strong></div>
            <div>こんにちは！何でもお気軽にお聞きください。</div>
            <div class="message-time">システム起動時</div>
        </div>
    `;
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('messageInput').focus();
    initializeProductMasterMCP();
    initializeCrmMCP();
});
