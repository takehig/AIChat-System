        // CRM MCP関連関数
        async function toggleCrmMCP() {
            console.log("CRM MCP toggle clicked");
            try {
                const response = await fetch("/aichat/api/mcp/crm/toggle", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" }
                });
                const result = await response.json();
                updateCrmMCPButton(result);
                alert(result.message || "CRM MCP状態を変更しました");
            } catch (error) {
                console.error("CRM MCP toggle error:", error);
                alert("CRM MCP状態の変更に失敗しました");
            }
        }

    const statusBadge = document.getElementById('crmStatus');
    const card = document.getElementById('crmCard');
    if (!btn || !statusBadge || !card) return;
    
    const mcpEnabled = status.crm_enabled || false;
    
    if (mcpEnabled) {
        btn.innerHTML = '<i class="fas fa-toggle-on me-1"></i> 無効化';
        btn.className = 'btn btn-info btn-sm w-100';
        statusBadge.textContent = 'ON';
        statusBadge.className = 'badge bg-success ms-auto';
        card.style.borderLeft = '4px solid #0dcaf0';
    } else {
        btn.innerHTML = '<i class="fas fa-toggle-off me-1"></i> 有効化';
        btn.className = 'btn btn-outline-info btn-sm w-100';
        statusBadge.textContent = 'OFF';
        statusBadge.className = 'badge bg-secondary ms-auto';
        card.style.borderLeft = 'none';
    }
}
