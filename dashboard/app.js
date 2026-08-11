// ============================================================================
// VMS PRO v4.0 SWING QUANT TERMINAL - COMPLETE FRONTEND CONTROLLER
// ============================================================================

let currentFilter = 'ALL';
let rawStockData = [];

// DOM Utility
function appendConsoleLog(message, isError = false) {
    const consoleLogBox = document.getElementById('console-log-box');
    if (!consoleLogBox) return;
    const timeStr = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.className = isError ? 'text-red-400 font-mono text-xs my-0.5' : 'text-emerald-400 font-mono text-xs my-0.5';
    logLine.innerText = `> [${timeStr}] ${message}`;
    consoleLogBox.appendChild(logLine);
    consoleLogBox.scrollTop = consoleLogBox.scrollHeight;
}

// Fetch Rankings API
async function fetchRankings() {
    try {
        appendConsoleLog("Fetching latest VMS PRO v4.0 Swing rankings...");
        const response = await fetch('/api/rankings');
        
        if (!response.ok) {
            throw new Error(`HTTP Error Status: ${response.status}`);
        }
        
        const resData = await response.json();
        rawStockData = resData.rankings || resData.data || (Array.isArray(resData) ? resData : []);
        
        const lastUpdatedEl = document.getElementById('last-updated');
        if (resData.last_updated && lastUpdatedEl) {
            lastUpdatedEl.innerText = resData.last_updated;
        }

        if (!rawStockData || rawStockData.length === 0) {
            appendConsoleLog("Warning: No evaluated stocks returned from backend.");
            renderTable([]);
            return;
        }

        appendConsoleLog(`Swing Rankings updated successfully. (${rawStockData.length} stocks evaluated)`);
        applyFilterAndRender();

    } catch (error) {
        appendConsoleLog(`Failed to fetch rankings: ${error.message}`, true);
        renderTable([]);
    }
}

// Render Rankings Table
function renderTable(stocks) {
    const tableBody = document.getElementById('rankings-table-body');
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!stocks || stocks.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-8 text-gray-500 font-mono">
                    No stocks matching filter criteria (${currentFilter}).
                </td>
            </tr>
        `;
        return;
    }

    stocks.forEach((stock, index) => {
        const row = document.createElement('tr');
        row.className = "border-b border-gray-800 hover:bg-gray-800/50 transition-colors font-mono text-sm";

        let scoreColorClass = "bg-red-900/40 text-red-400 border-red-700/50";
        if (stock.score >= 80) {
            scoreColorClass = "bg-emerald-900/40 text-emerald-400 border-emerald-700/50";
        } else if (stock.score >= 60) {
            scoreColorClass = "bg-amber-900/40 text-amber-400 border-amber-700/50";
        }

        let signalText = stock.signal || "NO TRADE";
        let signalColorClass = "text-gray-400";
        if (scoreColorClass.includes('emerald')) signalColorClass = "text-emerald-400 font-bold";
        if (scoreColorClass.includes('amber')) signalColorClass = "text-amber-400 font-bold";

        row.innerHTML = `
            <td class="py-3 px-4 text-gray-400">#${stock.rank || index + 1}</td>
            <td class="py-3 px-4 text-white font-bold">${stock.symbol}</td>
            <td class="py-3 px-4">
                <span class="px-2.5 py-1 rounded border text-xs font-bold ${scoreColorClass}">
                    ${stock.score} / 100
                </span>
            </td>
            <td class="py-3 px-4 text-gray-300 text-xs">
                ${stock.monthly_pivot || `Monthly: ₹${stock.m_pivot || 0} | W-Pivot: ₹${stock.w_pivot || 0}`}
            </td>
            <td class="py-3 px-4 ${signalColorClass}">
                ${stock.swing_signal || `${signalText} | RS PERCENTILE > ${stock.rs_rank || 50}`}
            </td>
            <td class="py-3 px-4">
                <button onclick="openRiskModal('${stock.symbol}', ${stock.price || 0}, ${stock.atr || 10})" 
                        class="px-3 py-1 bg-blue-600/30 hover:bg-blue-600/60 border border-blue-500/50 text-blue-300 rounded text-xs transition-all">
                    Risk Plan
                </button>
            </td>
        `;

        tableBody.appendChild(row);
    });
}

// Filter Options
function setFilter(filterType) {
    currentFilter = filterType;
    applyFilterAndRender();
}

function applyFilterAndRender() {
    if (currentFilter === 'VALID') {
        const filtered = rawStockData.filter(s => s.score >= 80);
        renderTable(filtered);
    } else if (currentFilter === 'WATCHLIST') {
        const filtered = rawStockData.filter(s => s.score >= 60 && s.score < 80);
        renderTable(filtered);
    } else {
        renderTable(rawStockData);
    }
}

// WebSocket Live Stream Engine
function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/live-ticks`;

    const feedStatusEl = document.getElementById('feed-status');
    const ticksReceivedEl = document.getElementById('ticks-received');

    appendConsoleLog(`Connecting WebSocket to ${wsUrl}...`);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        appendConsoleLog("Live Feed WebSocket Connection Established.");
        if (feedStatusEl) {
            feedStatusEl.innerText = "CONNECTED";
            feedStatusEl.className = "text-emerald-500 font-bold font-mono mt-1";
        }
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'ping' || data.type === 'tick' || data.type === 'status') {
                if (ticksReceivedEl) {
                    let currentTicks = parseInt(ticksReceivedEl.innerText || '0');
                    ticksReceivedEl.innerText = currentTicks + 1;
                }
            }
            if (data.type === 'log') {
                appendConsoleLog(data.message);
                fetchRankings();
            }
        } catch (e) {
            console.error("WS Parse error", e);
        }
    };

    ws.onclose = () => {
        appendConsoleLog("Live WebSocket Stream Disconnected. Reconnecting in 3s...", true);
        if (feedStatusEl) {
            feedStatusEl.innerText = "DISCONNECTED";
            feedStatusEl.className = "text-red-500 font-bold font-mono mt-1";
        }
        setTimeout(connectWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error("WebSocket Error:", err);
        ws.close();
    };
}

// Risk Modal Action
function openRiskModal(symbol, price, atr) {
    const stopLoss = (price - (2.0 * atr)).toFixed(2);
    const target1 = (price + (3.0 * atr)).toFixed(2);
    const target2 = (price + (5.0 * atr)).toFixed(2);
    
    alert(`📊 VMS PRO v4 RISK PLANNER FOR ${symbol}\n\n` +
          `• Current Price: ₹${price}\n` +
          `• Calculated ATR (14): ₹${atr}\n` +
          `-----------------------------------\n` +
          `🛑 Stop Loss (2 ATR): ₹${stopLoss}\n` +
          `🎯 Target 1 (1:1.5 RR): ₹${target1}\n` +
          `🚀 Target 2 (1:2.5 RR): ₹${target2}`
    );
}

// Auto Startup
document.addEventListener("DOMContentLoaded", () => {
    fetchRankings();
    connectWebSocket();
});