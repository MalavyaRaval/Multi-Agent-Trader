// ============================================================
// DASHBOARD.JS
// ============================================================


// ============================================================
// GLOBAL STATE
// ============================================================

let priceChart = null;
let rsiChart = null;
let macdChart = null;
let equityChart = null;
let portfolioChartInstance = null;

let commIndex = 0;
let currentAnalysisResult = null;
let currentSessionFilter = "";
let currentCategoryFilter = "";

const agentAvatars = {
    orchestrator: {
        avatar: "🤖",
        color: "#60a5fa"
    },

    market_agent: {
        avatar: "📊",
        color: "#38bdf8"
    },

    technical_agent: {
        avatar: "📈",
        color: "#c084fc"
    },

    fundamental_agent: {
        avatar: "🏦",
        color: "#fbbf24"
    },

    news_agent: {
        avatar: "📰",
        color: "#f472b6"
    },

    risk_agent: {
        avatar: "🛡️",
        color: "#fb7185"
    },

    portfolio_agent: {
        avatar: "💼",
        color: "#2dd4bf"
    },

    execution_agent: {
        avatar: "🎯",
        color: "#34d399"
    },

    user: {
        avatar: "👤",
        color: "#60a5fa"
    }
};


// ============================================================
// SHARED HELPERS
// ============================================================

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function fmtMoney(value) {
    if (
        value === undefined ||
        value === null ||
        isNaN(value)
    ) {
        return "$0.00";
    }

    return "$" + parseFloat(value).toLocaleString(
        undefined,
        {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }
    );
}


function fmtNum(value, decimals = 2) {
    if (
        value === undefined ||
        value === null ||
        isNaN(value)
    ) {
        return "N/A";
    }

    return parseFloat(value).toFixed(decimals);
}


// ============================================================
// MODALS & TABS
// ============================================================

function openModal(id) {
    const modal = document.getElementById(id);

    if (!modal) {
        console.warn(`Modal not found: ${id}`);
        return;
    }

    modal.style.display = "flex";

    if (id === "diag-modal") {
        fetchDiagnostics();
    }
}


function closeModal(id) {
    const modal = document.getElementById(id);

    if (modal) {
        modal.style.display = "none";
    }
}


function switchTab(name, btn) {
    document
        .querySelectorAll(".tab-btn")
        .forEach(button => {
            button.classList.remove("active");
        });

    document
        .querySelectorAll(".tab-content")
        .forEach(content => {
            content.classList.remove("active");
        });

    if (btn) {
        btn.classList.add("active");
    }

    const tab = document.getElementById(
        "tab-" + name
    );

    if (tab) {
        tab.classList.add("active");
    }
}


// ============================================================
// DIAGNOSTICS
// ============================================================

function fetchDiagnostics() {
    fetch("/api/diagnostics")
        .then(response => response.json())
        .then(data => {
            const services = data.services || {};

            const alpaca = services.alpaca || {};
            const finnhub = services.finnhub || {};
            const gemini = services.gemini || {};

            const alpacaDot =
                document.getElementById("alpaca-dot");

            if (alpacaDot) {
                alpacaDot.className =
                    alpaca.keys_configured
                        ? "status-dot dot-green"
                        : "status-dot dot-yellow";
            }

            const alpacaLabel =
                document.getElementById("alpaca-label");

            if (alpacaLabel) {
                alpacaLabel.textContent =
                    alpaca.keys_configured
                        ? "Alpaca API: Ready"
                        : "Alpaca API: Setup needed";
            }

            const finnhubDot =
                document.getElementById("finnhub-dot");

            if (finnhubDot) {
                finnhubDot.className =
                    finnhub.keys_configured
                        ? "status-dot dot-green"
                        : "status-dot dot-yellow";
            }

            const geminiDot =
                document.getElementById("gemini-dot");

            if (geminiDot) {
                geminiDot.className =
                    gemini.keys_configured
                        ? "status-dot dot-green"
                        : "status-dot dot-yellow";
            }

            const body =
                document.getElementById(
                    "diag-modal-body"
                );

            if (!body) {
                return;
            }

            body.innerHTML = "";

            Object.entries(services).forEach(
                ([key, svc]) => {
                    const isOk =
                        !!svc.keys_configured;

                    const statusColor =
                        isOk
                            ? "#34d399"
                            : "#fbbf24";

                    const card =
                        document.createElement(
                            "div"
                        );

                    card.className = "card";

                    card.innerHTML = `
                        <div style="
                            display:flex;
                            justify-content:space-between;
                            align-items:center;
                            margin-bottom:6px;
                        ">
                            <strong style="
                                font-size:1rem;
                                color:#e5e7eb;
                            ">
                                ${escapeHtml(
                        svc.name || key
                    )}
                            </strong>

                            <span
                                class="category-tag"
                                style="
                                    background:${isOk
                            ? "rgba(16,185,129,0.15)"
                            : "rgba(245,158,11,0.15)"
                        };
                                    color:${statusColor};
                                "
                            >
                                ${isOk
                            ? "🟢 CONNECTED"
                            : "🟡 FALLBACK ACTIVE"
                        }
                            </span>
                        </div>

                        ${svc.purpose ? `
                        <div style="font-size:0.82rem; color:var(--text-main); margin-bottom:2px;">
                            <strong>Purpose:</strong> ${escapeHtml(svc.purpose)}
                        </div>` : ""}

                        ${svc.feed ? `
                        <div style="font-size:0.82rem; color:var(--text-main); margin-bottom:2px;">
                            <strong>Feed:</strong> ${escapeHtml(svc.feed)}
                        </div>` : ""}

                        ${typeof svc.market_hours_open === "boolean" ? `
                        <div style="font-size:0.82rem; color:var(--text-main); margin-bottom:2px;">
                            <strong>Market Hours:</strong> ${svc.market_hours_open ? "Open (regular session)" : "Closed"}
                        </div>` : ""}

                        ${svc.rate_limit ? `
                        <div style="font-size:0.82rem; color:var(--text-main); margin-bottom:2px;">
                            <strong>Requests (60s):</strong> ${svc.rate_limit.requests_last_60s} / ${svc.rate_limit.limit_per_minute}
                        </div>` : ""}

                        <div style="
                            font-size:0.82rem;
                            color:var(--text-muted);
                        ">
                            ${escapeHtml(
                            svc.note ||
                            svc.mode ||
                            ""
                        )}
                        </div>
                    `;

                    body.appendChild(card);
                }
            );
        })
        .catch(error => {
            console.error(
                "Diagnostics error:",
                error
            );
        });
}


// ============================================================
// ACCOUNT & POSITIONS
// ============================================================

function refreshAccount() {
    fetch("/api/account")
        .then(response => response.json())
        .then(data => {
            if (data.cash !== undefined) {
                const cash =
                    document.getElementById(
                        "acc-cash"
                    );

                const portfolio =
                    document.getElementById(
                        "acc-portfolio"
                    );

                const bp =
                    document.getElementById(
                        "acc-bp"
                    );

                const equity =
                    document.getElementById(
                        "acc-equity"
                    );

                if (cash) {
                    cash.textContent =
                        fmtMoney(data.cash);
                }

                if (portfolio) {
                    portfolio.textContent =
                        fmtMoney(
                            data.portfolio_value
                        );
                }

                if (bp) {
                    bp.textContent =
                        fmtMoney(
                            data.buying_power
                        );
                }

                if (equity) {
                    equity.textContent =
                        fmtMoney(data.equity);
                }
            }
        })
        .catch(() => { });


    fetch("/api/positions")
        .then(response => response.json())
        .then(data => {
            const container =
                document.getElementById(
                    "positions-container"
                );

            if (!container) {
                return;
            }

            const positions =
                data.all_positions || [];

            if (!positions.length) {
                container.innerHTML = `
                    <div style="
                        color:var(--text-muted);
                        padding:8px 0;
                        text-align:center;
                    ">
                        No open positions
                    </div>
                `;

                return;
            }

            let html = `
                <table class="custom-table">
                    <thead>
                        <tr>
                            <th>Symbol</th>
                            <th style="text-align:right;">
                                Qty
                            </th>
                            <th style="text-align:right;">
                                Avg $
                            </th>
                            <th style="text-align:right;">
                                P&amp;L
                            </th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            positions.forEach(position => {
                const qtyVal =
                    parseFloat(
                        position.qty || 0
                    );

                const qtyFormatted =
                    qtyVal >= 1
                        ? qtyVal.toFixed(2)
                        : qtyVal > 0
                            ? qtyVal.toFixed(4)
                            : "0";

                const avgPrice =
                    parseFloat(
                        position.avg_entry_price ||
                        0
                    );

                const pnl =
                    parseFloat(
                        position.unrealized_pl ||
                        0
                    );

                const pnlColor =
                    pnl > 0
                        ? "#34d399"
                        : pnl < 0
                            ? "#fb7185"
                            : "var(--text-muted)";

                const pnlFormatted =
                    (pnl >= 0 ? "+$" : "-$") +
                    Math.abs(pnl).toLocaleString(
                        undefined,
                        {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        }
                    );

                html += `
                    <tr>
                        <td>
                            <strong style="
                                color:#e5e7eb;
                            ">
                                ${escapeHtml(
                    position.symbol
                )}
                            </strong>
                        </td>

                        <td style="
                            text-align:right;
                            font-family:
                                'JetBrains Mono',
                                monospace;
                            font-size:0.78rem;
                        "
                        title="${escapeHtml(
                    position.qty
                )}">
                            ${qtyFormatted}
                        </td>

                        <td style="
                            text-align:right;
                            font-family:
                                'JetBrains Mono',
                                monospace;
                            font-size:0.78rem;
                        ">
                            ${fmtMoney(avgPrice)}
                        </td>

                        <td style="
                            text-align:right;
                            font-family:
                                'JetBrains Mono',
                                monospace;
                            font-size:0.78rem;
                            font-weight:600;
                            color:${pnlColor};
                        ">
                            ${pnlFormatted}
                        </td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
            `;

            container.innerHTML = html;
        })
        .catch(() => { });
}


// ============================================================
// AUTONOMOUS LOOP CONTROLS
// ============================================================

function startAutonomous() {
    const symbols = prompt(
        "Enter symbols to auto-trade (comma separated):",
        "AAPL, TSLA, GOOGL"
    );

    if (!symbols) {
        return;
    }

    const symbolList =
        symbols
            .split(",")
            .map(symbol =>
                symbol.trim().toUpperCase()
            )
            .filter(Boolean);

    if (!symbolList.length) {
        return;
    }

    fetch("/api/autonomous/start", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            symbols: symbolList,
            interval_seconds: 180
        })
    })
        .then(response => response.json())
        .then(() => {
            const status =
                document.getElementById(
                    "autonomous-status"
                );

            if (!status) {
                return;
            }

            status.textContent =
                "Running loop for " +
                symbolList.join(", ");

            status.style.color = "#34d399";

            fetchAutonomousStatus();
        })
        .catch(error => {
            console.error(
                "Autonomous start error:",
                error
            );
        });
}


function stopAutonomous() {
    fetch("/api/autonomous/stop", {
        method: "POST"
    })
        .then(response => response.json())
        .then(() => {
            const status =
                document.getElementById(
                    "autonomous-status"
                );

            if (!status) {
                return;
            }

            status.textContent =
                "Status: Stopped";

            status.style.color =
                "var(--text-muted)";

            fetchAutonomousStatus();
        })
        .catch(error => {
            console.error(
                "Autonomous stop error:",
                error
            );
        });
}


// PHASES_PLAN.md Phase 9 -- Autonomous Loop Monitor
const AUTO_STATUS_ICON = {
    SUCCESS: "🟢",
    WARNING: "🟡",
    ERROR: "🔴"
};

function fmtClockTime(isoString) {
    if (!isoString) {
        return "-";
    }
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
        return "-";
    }
    return date.toLocaleTimeString();
}

function fetchAutonomousStatus() {
    fetch("/api/autonomous/status")
        .then(response => response.json())
        .then(data => {
            const monitor = document.getElementById("autonomous-monitor");
            if (!monitor || !data) {
                return;
            }

            monitor.style.display = data.status === "running" || (data.runs_today || 0) > 0
                ? "block"
                : "none";

            const setText = (id, text) => {
                const el = document.getElementById(id);
                if (el) {
                    el.textContent = text;
                }
            };

            setText("auto-interval", data.interval_seconds ? `${data.interval_seconds}s` : "-");
            setText("auto-symbols", (data.symbols || []).join(", ") || "-");
            setText("auto-last-run", fmtClockTime(data.last_run_at));
            setText("auto-next-run", data.status === "running" ? fmtClockTime(data.next_run_at) : "-");
            setText("auto-runs-today", data.runs_today ?? 0);
            setText(
                "auto-run-outcomes",
                `${data.successful ?? 0} / ${data.warnings ?? 0} / ${data.errors ?? 0}`
            );
            setText(
                "auto-action-counts",
                `${data.buy_count ?? 0} / ${data.sell_count ?? 0} / ${data.hold_count ?? 0}`
            );

            const recentContainer = document.getElementById("auto-recent-runs");
            if (recentContainer) {
                const runs = (data.recent_runs || []).slice(0, 8);
                recentContainer.innerHTML = runs.map(run => {
                    const icon = AUTO_STATUS_ICON[run.status] || "⚪";
                    const warningsText = (run.warnings || []).length
                        ? ` — ${escapeHtml(run.warnings.join("; "))}`
                        : "";
                    return `
                        <div style="padding:3px 0; border-top:1px solid var(--border-color);">
                            ${icon} ${escapeHtml(run.symbol)} ${escapeHtml((run.action || "hold").toUpperCase())}
                            (${fmtNum(run.duration_seconds, 1)}s)${warningsText}
                        </div>
                    `;
                }).join("");
            }
        })
        .catch(() => { })
        .finally(() => {
            setTimeout(fetchAutonomousStatus, 5000);
        });
}


// PHASES_PLAN.md Phase 12 -- Error Tracking
const ERROR_ICON = {
    RateLimitError: "🔴",
    AuthenticationError: "🔴",
    ServerError: "🔴",
    HTTPError: "🟡",
    TimeoutError: "🟡",
    NotConfiguredError: "🟡",
    UnknownError: "🟡"
};

function fetchErrors() {
    fetch("/api/errors?limit=20")
        .then(response => response.json())
        .then(data => {
            const panel = document.getElementById("errors-panel");
            if (!panel) {
                return;
            }

            const errors = data.errors || [];
            if (!errors.length) {
                panel.innerHTML = '<div style="color:var(--text-muted); font-style:italic;">No errors recorded yet.</div>';
                return;
            }

            panel.innerHTML = errors.map(err => {
                const icon = ERROR_ICON[err.error_type] || "🟡";
                const time = fmtClockTime(err.timestamp);
                const codeText = err.status_code ? ` ${err.status_code}` : "";
                return `
                    <div style="padding:4px 0; border-top:1px solid var(--border-color);">
                        <div>${icon} ${time} — ${escapeHtml(err.provider || err.agent || err.stage)}${codeText}</div>
                        <div style="color:var(--text-muted); font-size:0.72rem;">
                            ${escapeHtml(err.symbol || "")} · ${escapeHtml(err.message || "")}
                        </div>
                    </div>
                `;
            }).join("");
        })
        .catch(() => { })
        .finally(() => {
            setTimeout(fetchErrors, 8000);
        });
}


// ============================================================
// ANALYSIS PIPELINE
// ============================================================

function runAnalysis() {
    const symbolInput =
        document.getElementById(
            "analysis-symbol"
        );

    const timeframeInput =
        document.getElementById(
            "analysis-timeframe"
        );

    const symbol =
        symbolInput?.value
            .trim()
            .toUpperCase() ||
        "AAPL";

    const timeframeMode =
        timeframeInput?.value ||
        "single";

    const endpoint =
        timeframeMode === "multi"
            ? "/api/multiframe"
            : "/api/analyze";

    const results =
        document.getElementById(
            "analysis-results"
        );

    const loading =
        document.getElementById(
            "analysis-loading"
        );

    if (results) {
        results.style.display = "none";
    }

    if (loading) {
        loading.style.display = "block";
    }

    fetch(endpoint, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            symbol
        })
    })
        .then(response => response.json())
        .then(data => {
            if (loading) {
                loading.style.display = "none";
            }

            currentAnalysisResult = data;

            renderAnalysisView(data);

            loadFinancialCharts(symbol);

            fetchSessions();
        })
        .catch(error => {
            if (loading) {
                loading.style.display = "none";
            }

            console.error(
                "Analysis failed:",
                error
            );

            alert(
                "Analysis failed: " +
                error.message
            );
        });
}


function renderAnalysisView(data) {
    const results =
        document.getElementById(
            "analysis-results"
        );

    if (results) {
        results.style.display = "flex";
    }

    const analyses =
        data.analyses || {};

    const execution =
        analyses.execution || {};

    const reasoning =
        execution.detailed_reasoning || {};

    const action =
        (
            execution.action ||
            "hold"
        ).toLowerCase();

    const confidence =
        parseFloat(
            execution.confidence || 0
        ) * 100;

    const badge =
        document.getElementById(
            "decision-badge"
        );

    if (badge) {
        badge.textContent =
            action.toUpperCase();

        badge.className =
            "badge-large badge-" +
            action;
    }

    const ticker =
        document.getElementById(
            "decision-ticker"
        );

    if (ticker) {
        ticker.textContent =
            `${data.symbol || ""} Multi-Agent Decision`;
    }

    const timestamp =
        document.getElementById(
            "decision-timestamp"
        );

    if (timestamp) {
        timestamp.textContent =
            `Session: ${data.session_id ||
            "Manual Run"
            } @ ${new Date(
                data.timestamp ||
                Date.now()
            ).toLocaleTimeString()
            }`;
    }

    const metricConfidence =
        document.getElementById(
            "metric-confidence"
        );

    if (metricConfidence) {
        metricConfidence.textContent =
            confidence.toFixed(0) + "%";
    }

    const metricCombined =
        document.getElementById(
            "metric-combined"
        );

    if (metricCombined) {
        metricCombined.textContent =
            fmtNum(execution.raw_score);
    }

    const metricAgent =
        document.getElementById(
            "metric-agent"
        );

    if (metricAgent) {
        metricAgent.textContent =
            fmtNum(execution.agent_score);
    }

    const metricStrategy =
        document.getElementById(
            "metric-strat"
        );

    if (metricStrategy) {
        metricStrategy.textContent =
            fmtNum(execution.strategy_score);
    }

    const executive =
        document.getElementById(
            "reasoning-executive"
        );

    if (executive) {
        executive.textContent =
            reasoning.executive_summary ||
            execution.reason ||
            "Decision computed.";
    }


    // --------------------------------------------------------
    // Bullish Arguments
    // --------------------------------------------------------

    const bullishList =
        document.getElementById(
            "bullish-list"
        );

    if (bullishList) {
        const bullish =
            reasoning.bullish_arguments ||
            [];

        bullishList.innerHTML =
            bullish
                .map(argument =>
                    `<li>${escapeHtml(argument)}</li>`
                )
                .join("") ||
            "<li>No major bullish factors</li>";
    }


    // --------------------------------------------------------
    // Bearish Arguments
    // --------------------------------------------------------

    const bearishList =
        document.getElementById(
            "bearish-list"
        );

    if (bearishList) {
        const bearish =
            reasoning.bearish_arguments ||
            [];

        bearishList.innerHTML =
            bearish
                .map(argument =>
                    `<li>${escapeHtml(argument)}</li>`
                )
                .join("") ||
            "<li>No major bearish threats</li>";
    }


    const riskSummary =
        document.getElementById(
            "risk-summary-text"
        );

    if (riskSummary) {
        riskSummary.textContent =
            reasoning.risk_assessment ||
            "Medium risk";
    }


    const strategySummary =
        document.getElementById(
            "strat-summary-text"
        );

    if (strategySummary) {
        strategySummary.textContent =
            reasoning.strategy_summary ||
            "5 Strategies voted";
    }


    // --------------------------------------------------------
    // Strategy Cards
    // --------------------------------------------------------

    const strategyGrid =
        document.getElementById(
            "strategies-grid"
        );

    if (strategyGrid) {
        strategyGrid.innerHTML = "";

        (
            execution.strategy_votes ||
            []
        ).forEach(vote => {
            const decision =
                (
                    vote.decision ||
                    "hold"
                ).toLowerCase();

            const voteConfidence =
                parseFloat(
                    vote.confidence || 0
                ) * 100;

            const card =
                document.createElement(
                    "div"
                );

            card.className =
                "strategy-card";

            card.innerHTML = `
                <div class="strategy-header">

                    <span class="strategy-name">
                        ${escapeHtml(
                vote.strategy ||
                vote.name ||
                "Strategy"
            )}
                    </span>

                    <span
                        class="
                            status-pill
                            badge-${escapeHtml(
                decision
            )}
                        "
                        style="
                            padding:2px 8px;
                            font-size:0.75rem;
                        "
                    >
                        ${escapeHtml(
                decision.toUpperCase()
            )}
                    </span>

                </div>

                <div style="
                    font-size:0.8rem;
                    color:var(--text-muted);
                    display:flex;
                    justify-content:space-between;
                ">
                    <span>
                        Confidence:
                        ${voteConfidence.toFixed(0)}%
                    </span>

                    <span>
                        Score:
                        ${fmtNum(vote.raw_score)}
                    </span>
                </div>

                <div class="strategy-reason">
                    ${escapeHtml(
                vote.reason ||
                "No strategy notes"
            )}
                </div>
            `;

            strategyGrid.appendChild(card);
        });
    }


    // --------------------------------------------------------
    // Agent Cards
    // --------------------------------------------------------

    const agentsGrid =
        document.getElementById(
            "agents-grid"
        );

    if (!agentsGrid) {
        return;
    }

    agentsGrid.innerHTML = "";


    const market =
        analyses.market?.metrics || {};

    agentsGrid.appendChild(
        createAgentCard(
            "Market Data Agent",
            `
                <div class="stat-row">
                    <span>Spread:</span>
                    <strong>
                        ${fmtNum(market.spread)}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Rel Volume:</span>
                    <strong>
                        ${fmtNum(
                market.relative_volume
            )}x
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Gap %:</span>
                    <strong>
                        ${fmtNum(
                market.gap_percent
            )}%
                    </strong>
                </div>
            `
        )
    );


    const technical =
        analyses.technical?.signals || {};

    agentsGrid.appendChild(
        createAgentCard(
            "Technical Analyst",
            `
                <div class="stat-row">
                    <span>RSI (14):</span>
                    <strong>
                        ${fmtNum(
                technical.rsi_14
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>MACD:</span>
                    <strong>
                        ${fmtNum(
                technical.macd
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>EMA 20:</span>
                    <strong>
                        ${fmtNum(
                technical.ema_20
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>ATR (14):</span>
                    <strong>
                        ${fmtNum(
                technical.atr_14
            )}
                    </strong>
                </div>
            `
        )
    );


    const fundamental =
        analyses.fundamental?.data?.company ||
        {};

    agentsGrid.appendChild(
        createAgentCard(
            "Fundamental Agent",
            `
                <div class="stat-row">
                    <span>P/E Ratio:</span>
                    <strong>
                        ${fmtNum(
                fundamental.pe_ratio
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>EPS:</span>
                    <strong>
                        ${fmtNum(
                fundamental.eps
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Beta:</span>
                    <strong>
                        ${fmtNum(
                fundamental.beta
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Market Cap:</span>
                    <strong>
                        ${fundamental.market_cap
                ? "$" +
                Math.round(
                    fundamental.market_cap
                ).toLocaleString() +
                "M"
                : "N/A"
            }
                    </strong>
                </div>
            `
        )
    );


    const news =
        analyses.news || {};

    agentsGrid.appendChild(
        createAgentCard(
            "News & Sentiment Agent",
            `
                <div class="stat-row">
                    <span>Sentiment:</span>
                    <strong style="
                        text-transform:uppercase;
                    ">
                        ${escapeHtml(
                news.sentiment ||
                "neutral"
            )}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Articles Scanned:</span>
                    <strong>
                        ${(
                news.articles ||
                []
            ).length
            }
                    </strong>
                </div>
            `
        )
    );


    const risk =
        analyses.risk || {};

    const riskLevel =
        risk.risk_level ||
        "medium";

    agentsGrid.appendChild(
        createAgentCard(
            "Risk Evaluator",
            `
                <div class="stat-row">
                    <span>Risk Level:</span>

                    <strong style="
                        text-transform:uppercase;
                        color:${riskLevel === "high"
                ? "#fb7185"
                : "#34d399"
            };
                    ">
                        ${escapeHtml(riskLevel)}
                    </strong>
                </div>

                <div class="stat-row">
                    <span>ATR Volatility %:</span>

                    <strong>
                        ${fmtNum(
                risk.checks?.atr_percent
            )}%
                    </strong>
                </div>
            `
        )
    );


    const portfolio =
        analyses.portfolio?.position || {};

    agentsGrid.appendChild(
        createAgentCard(
            "Portfolio Tracker",
            `
                <div class="stat-row">
                    <span>Current Position:</span>

                    <strong>
                        ${portfolio.qty
                ? escapeHtml(
                    portfolio.qty
                ) + " shares"
                : "Flat (0)"
            }
                    </strong>
                </div>

                <div class="stat-row">
                    <span>Unrealized P&amp;L:</span>

                    <strong>
                        ${portfolio.unrealized_pl
                ? fmtMoney(
                    portfolio.unrealized_pl
                )
                : "$0.00"
            }
                    </strong>
                </div>
            `
        )
    );
}


function createAgentCard(title, bodyHtml) {
    const card =
        document.createElement("div");

    card.className =
        "agent-card";

    card.innerHTML = `
        <h4>${escapeHtml(title)}</h4>
        ${bodyHtml}
    `;

    return card;
}


// ============================================================
// FINANCIAL CHARTS
// ============================================================

function loadFinancialCharts(symbol) {
    fetch("/api/chart_data", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            symbol,
            days: 90
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status !== "ok") {
                return;
            }

            const labels =
                data.dates || [];


            // ------------------------------------------------
            // Price Chart
            // ------------------------------------------------

            const priceCanvas =
                document.getElementById(
                    "priceChart"
                );

            if (priceCanvas) {
                const ctxPrice =
                    priceCanvas.getContext("2d");

                if (ctxPrice) {
                    if (priceChart) {
                        priceChart.destroy();
                    }

                    priceChart =
                        new Chart(
                            ctxPrice,
                            {
                                type: "line",

                                data: {
                                    labels,

                                    datasets: [
                                        {
                                            label:
                                                "Close Price",

                                            data:
                                                data.close,

                                            borderColor:
                                                "#3b82f6",

                                            borderWidth: 2,

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "EMA (20)",

                                            data:
                                                data.ema20,

                                            borderColor:
                                                "#10b981",

                                            borderWidth: 1.5,

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "EMA (50)",

                                            data:
                                                data.ema50,

                                            borderColor:
                                                "#f59e0b",

                                            borderWidth: 1.5,

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "Bollinger Upper",

                                            data:
                                                data.bollinger_upper,

                                            borderColor:
                                                "rgba(139,92,246,0.5)",

                                            borderWidth: 1,

                                            borderDash: [
                                                4,
                                                4
                                            ],

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "Bollinger Lower",

                                            data:
                                                data.bollinger_lower,

                                            borderColor:
                                                "rgba(139,92,246,0.5)",

                                            borderWidth: 1,

                                            borderDash: [
                                                4,
                                                4
                                            ],

                                            pointRadius: 0
                                        }
                                    ]
                                },

                                options: {
                                    responsive: true,

                                    maintainAspectRatio:
                                        false,

                                    plugins: {
                                        legend: {
                                            labels: {
                                                color:
                                                    "#9ca3af",

                                                font: {
                                                    family:
                                                        "Inter",

                                                    size: 11
                                                }
                                            }
                                        }
                                    },

                                    scales: {
                                        x: {
                                            ticks: {
                                                color:
                                                    "#6b7280",

                                                maxTicksLimit:
                                                    12
                                            }
                                        },

                                        y: {
                                            ticks: {
                                                color:
                                                    "#6b7280"
                                            }
                                        }
                                    }
                                }
                            }
                        );
                }
            }


            // ------------------------------------------------
            // RSI Chart
            // ------------------------------------------------

            const rsiCanvas =
                document.getElementById(
                    "rsiChart"
                );

            if (rsiCanvas) {
                const ctxRsi =
                    rsiCanvas.getContext("2d");

                if (ctxRsi) {
                    if (rsiChart) {
                        rsiChart.destroy();
                    }

                    rsiChart =
                        new Chart(
                            ctxRsi,
                            {
                                type: "line",

                                data: {
                                    labels,

                                    datasets: [
                                        {
                                            label:
                                                "RSI (14)",

                                            data:
                                                data.rsi,

                                            borderColor:
                                                "#a78bfa",

                                            borderWidth: 1.5,

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "Overbought (70)",

                                            data:
                                                labels.map(
                                                    () => 70
                                                ),

                                            borderColor:
                                                "#f43f5e",

                                            borderWidth: 1,

                                            borderDash: [
                                                2,
                                                2
                                            ],

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "Oversold (30)",

                                            data:
                                                labels.map(
                                                    () => 30
                                                ),

                                            borderColor:
                                                "#34d399",

                                            borderWidth: 1,

                                            borderDash: [
                                                2,
                                                2
                                            ],

                                            pointRadius: 0
                                        }
                                    ]
                                },

                                options: {
                                    responsive: true,

                                    maintainAspectRatio:
                                        false,

                                    plugins: {
                                        legend: {
                                            display: false
                                        }
                                    },

                                    scales: {
                                        x: {
                                            display: false
                                        },

                                        y: {
                                            min: 0,

                                            max: 100,

                                            ticks: {
                                                color:
                                                    "#6b7280"
                                            }
                                        }
                                    }
                                }
                            }
                        );
                }
            }


            // ------------------------------------------------
            // MACD Chart
            // ------------------------------------------------

            const macdCanvas =
                document.getElementById(
                    "macdChart"
                );

            if (macdCanvas) {
                const ctxMacd =
                    macdCanvas.getContext("2d");

                if (ctxMacd) {
                    if (macdChart) {
                        macdChart.destroy();
                    }

                    macdChart =
                        new Chart(
                            ctxMacd,
                            {
                                type: "bar",

                                data: {
                                    labels,

                                    datasets: [
                                        {
                                            type: "line",

                                            label: "MACD",

                                            data:
                                                data.macd,

                                            borderColor:
                                                "#60a5fa",

                                            borderWidth: 1.5,

                                            pointRadius: 0
                                        },

                                        {
                                            type: "line",

                                            label: "Signal",

                                            data:
                                                data.macd_signal,

                                            borderColor:
                                                "#f59e0b",

                                            borderWidth: 1.5,

                                            pointRadius: 0
                                        },

                                        {
                                            label:
                                                "Histogram",

                                            data:
                                                data.macd_hist,

                                            backgroundColor:
                                                (
                                                    data.macd_hist ||
                                                    []
                                                ).map(
                                                    value =>
                                                        value >= 0
                                                            ? "rgba(16,185,129,0.4)"
                                                            : "rgba(244,63,94,0.4)"
                                                )
                                        }
                                    ]
                                },

                                options: {
                                    responsive: true,

                                    maintainAspectRatio:
                                        false,

                                    plugins: {
                                        legend: {
                                            display: false
                                        }
                                    },

                                    scales: {
                                        x: {
                                            display: false
                                        },

                                        y: {
                                            ticks: {
                                                color:
                                                    "#6b7280"
                                            }
                                        }
                                    }
                                }
                            }
                        );
                }
            }
        })
        .catch(error => {
            console.error(
                "Financial chart error:",
                error
            );
        });
}


// ============================================================
// GROUP CHAT WORKSPACE
// ============================================================

function fetchSessions() {
    fetch("/api/sessions")
        .then(response => response.json())
        .then(data => {
            const select =
                document.getElementById(
                    "chat-session-select"
                );

            if (!select) {
                return;
            }

            select.innerHTML =
                '<option value="">Live Feed (All Runs)</option>';

            (
                data.sessions || []
            )
                .slice()
                .reverse()
                .forEach(session => {
                    const timeStr =
                        new Date(
                            session.timestamp ||
                            Date.now()
                        ).toLocaleTimeString();

                    const option =
                        document.createElement(
                            "option"
                        );

                    option.value =
                        session.session_id;

                    option.textContent =
                        `${session.symbol} Run @ ${timeStr} (${session.session_id})`;

                    select.appendChild(option);
                });
        })
        .catch(error => {
            console.error(
                "Session fetch error:",
                error
            );
        });
}


function filterChatBySession() {
    const select =
        document.getElementById(
            "chat-session-select"
        );

    currentSessionFilter =
        select?.value || "";

    renderGroupChatFeed(true);

    // PHASES_PLAN.md Phase 10 -- show the "Full Report" link once a specific
    // run is selected (the run_id and session_id are the same value).
    const reportBtn = document.getElementById("view-run-report-btn");
    if (reportBtn) {
        reportBtn.style.display = currentSessionFilter ? "inline-block" : "none";
    }
}


function openSelectedRunReport() {
    if (currentSessionFilter) {
        window.open(`/run/${encodeURIComponent(currentSessionFilter)}`, "_blank");
    }
}


function filterChatCategory(category) {
    currentCategoryFilter =
        category || "";

    renderGroupChatFeed(true);
}


function clearGroupChat() {
    const stream =
        document.getElementById(
            "group-chat-stream"
        );

    if (stream) {
        stream.innerHTML = "";
    }
}


function renderGroupChatFeed(reset = false) {
    const stream =
        document.getElementById(
            "group-chat-stream"
        );

    if (!stream) {
        return;
    }

    if (reset) {
        stream.innerHTML = "";
    }

    let url =
        "/api/messages?since=0";

    if (currentSessionFilter) {
        url +=
            "&session_id=" +
            encodeURIComponent(
                currentSessionFilter
            );
    }

    if (currentCategoryFilter) {
        url +=
            "&category=" +
            encodeURIComponent(
                currentCategoryFilter
            );
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            stream.innerHTML = "";

            (
                data.messages || []
            ).forEach(message => {
                const fromKey =
                    (
                        message.from ||
                        "orchestrator"
                    ).toLowerCase();

                const avatarMeta =
                    agentAvatars[fromKey] || {
                        avatar: "🤖",
                        color: "#60a5fa"
                    };

                const timeStr =
                    new Date(
                        message.timestamp ||
                        Date.now()
                    ).toLocaleTimeString();

                let categoryClass =
                    "tag-dialogue";

                const categoryLabel =
                    message.category ||
                    "DIALOGUE";

                if (
                    message.category ===
                    "api_diagnostic"
                ) {
                    categoryClass =
                        message.status_code ===
                            "warning"
                            ? "tag-warning"
                            : "tag-api";
                }
                else if (
                    message.category ===
                    "decision_monologue"
                ) {
                    categoryClass =
                        "tag-monologue";
                }

                const row =
                    document.createElement(
                        "div"
                    );

                row.className =
                    "chat-message-row";

                row.innerHTML = `
                    <div
                        class="agent-avatar"
                        style="
                            border-color:
                                ${avatarMeta.color};
                        "
                    >
                        ${avatarMeta.avatar}
                    </div>

                    <div class="chat-bubble-box">

                        <div class="chat-bubble-meta">

                            <div>

                                <span
                                    class="agent-title"
                                    style="
                                        color:
                                            ${avatarMeta.color};
                                    "
                                >
                                    ${escapeHtml(
                    message.from
                )}
                                </span>

                                <span class="target-arrow">
                                    &rarr;
                                    ${escapeHtml(
                    message.to
                )}
                                </span>

                            </div>

                            <div style="
                                display:flex;
                                align-items:center;
                                gap:6px;
                            ">

                                <span
                                    class="
                                        category-tag
                                        ${categoryClass}
                                    "
                                >
                                    ${escapeHtml(
                    categoryLabel
                        .replace(
                            "_",
                            " "
                        )
                )}
                                </span>

                                <span style="
                                    color:var(--text-dim);
                                    font-size:0.75rem;
                                ">
                                    ${timeStr}
                                </span>

                            </div>

                        </div>

                        <div class="chat-bubble-text">
                            ${escapeHtml(
                    message.message
                )}
                        </div>

                    </div>
                `;

                stream.appendChild(row);
            });

            stream.scrollTop =
                stream.scrollHeight;
        })
        .catch(error => {
            console.error(
                "Group chat error:",
                error
            );
        });
}


// ============================================================
// SMART SIZING
// ============================================================

function openSizingModal() {
    openModal("sizing-modal");
}


function calculateSizing() {
    const method =
        document.getElementById(
            "size-method"
        )?.value;

    const equity =
        parseFloat(
            document.getElementById(
                "size-equity"
            )?.value
        );

    const price =
        parseFloat(
            document.getElementById(
                "size-price"
            )?.value
        );

    const atr =
        parseFloat(
            document.getElementById(
                "size-atr"
            )?.value
        );

    fetch("/api/sizing", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            equity,
            price,
            atr,
            method
        })
    })
        .then(response => response.json())
        .then(data => {
            const output =
                document.getElementById(
                    "sizing-output"
                );

            if (!output) {
                return;
            }

            if (data.status === "ok") {
                output.innerHTML = `
                    <div style="
                        color:#34d399;
                        font-size:1.1rem;
                    ">
                        Recommended Allocation:
                        ${data.shares} shares
                        (${fmtMoney(data.notional)})
                    </div>

                    <div style="
                        font-size:0.8rem;
                        color:var(--text-muted);
                        margin-top:4px;
                    ">
                        Calculated using
                        ${escapeHtml(
                    data.method ||
                    method
                )}
                        algorithm.
                    </div>
                `;
            }
            else {
                output.textContent =
                    "Error: " +
                    (
                        data.error ||
                        data.reason ||
                        "Calculation failed"
                    );
            }
        })
        .catch(error => {
            console.error(
                "Sizing error:",
                error
            );
        });
}


// ============================================================
// TRADE EXECUTION
// ============================================================

function execTradeFromBanner(side) {
    if (!currentAnalysisResult) {
        return;
    }

    const symbol =
        currentAnalysisResult.symbol;

    const qty = prompt(
        `Enter number of shares to ${String(
            side
        ).toUpperCase()} for ${symbol}:`,
        "5"
    );

    if (!qty) {
        return;
    }

    const quantity =
        parseFloat(qty);

    if (
        !Number.isFinite(quantity) ||
        quantity <= 0
    ) {
        alert(
            "Please enter a valid positive quantity."
        );

        return;
    }

    fetch("/api/execute", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            symbol,
            side,
            qty: quantity
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.status === "submitted") {
                alert(
                    `Order Submitted Successfully!\n` +
                    `Order ID: ${data.order_id}\n` +
                    `${String(side).toUpperCase()} ` +
                    `${data.qty} ${symbol}`
                );

                refreshAccount();

                loadPortfolioChart();
            }
            else {
                alert(
                    `Order Error: ${data.error ||
                    "Unknown error"
                    }`
                );
            }
        })
        .catch(error => {
            console.error(
                "Trade execution error:",
                error
            );

            alert(
                "Trade execution failed: " +
                error.message
            );
        });
}


// ============================================================
// DIRECT AGENT CHAT
// ============================================================

function sendChatMessage() {
    const input =
        document.getElementById(
            "chat-input"
        );

    const select =
        document.getElementById(
            "agent-chat-select"
        );

    const windowDiv =
        document.getElementById(
            "chat-window"
        );

    if (
        !input ||
        !select ||
        !windowDiv
    ) {
        return;
    }

    const message =
        input.value.trim();

    const agentId =
        select.value;

    if (!message) {
        return;
    }


    const userMessage =
        document.createElement("div");

    userMessage.style.alignSelf =
        "flex-end";

    userMessage.style.background =
        "var(--primary)";

    userMessage.style.color =
        "white";

    userMessage.style.padding =
        "8px 14px";

    userMessage.style.borderRadius =
        "12px";

    userMessage.style.fontSize =
        "0.88rem";

    userMessage.style.maxWidth =
        "80%";

    userMessage.textContent =
        message;

    windowDiv.appendChild(
        userMessage
    );

    input.value = "";

    windowDiv.scrollTop =
        windowDiv.scrollHeight;


    fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message,
            agent_id: agentId
        })
    })
        .then(response => response.json())
        .then(data => {
            const agentMessage =
                document.createElement(
                    "div"
                );

            agentMessage.style.alignSelf =
                "flex-start";

            agentMessage.style.background =
                "rgba(255,255,255,0.08)";

            agentMessage.style.padding =
                "8px 14px";

            agentMessage.style.borderRadius =
                "12px";

            agentMessage.style.fontSize =
                "0.88rem";

            agentMessage.style.maxWidth =
                "80%";

            agentMessage.innerHTML = `
                <div style="
                    font-weight:600;
                    font-size:0.75rem;
                    color:#60a5fa;
                    margin-bottom:4px;
                ">
                    ${escapeHtml(agentId)}
                </div>

                <div>
                    ${escapeHtml(
                data.response ||
                "No response received."
            )}
                </div>
            `;

            windowDiv.appendChild(
                agentMessage
            );

            windowDiv.scrollTop =
                windowDiv.scrollHeight;
        })
        .catch(error => {
            console.error(
                "Chat error:",
                error
            );
        });
}


// ============================================================
// SCREENER
// ============================================================

function runScreener() {
    const container =
        document.getElementById(
            "screener-grid"
        );

    if (!container) {
        return;
    }

    container.innerHTML = `
        <div style="color:var(--text-muted);">
            Scanning market watchlist...
        </div>
    `;

    fetch("/api/screen", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            top_n: 8
        })
    })
        .then(response => response.json())
        .then(data => {
            const candidates =
                data.top_candidates ||
                data.results ||
                [];

            if (!candidates.length) {
                container.innerHTML = `
                    <div style="
                        color:var(--text-muted);
                    ">
                        No candidates met
                        screening thresholds.
                    </div>
                `;

                return;
            }

            container.innerHTML = "";

            candidates.forEach(candidate => {
                const card =
                    document.createElement(
                        "div"
                    );

                card.className =
                    "card";

                const symbol =
                    candidate.symbol || "";

                const reasons =
                    candidate.reasons || [];

                card.innerHTML = `
                    <div style="
                        font-size:1.1rem;
                        font-weight:700;
                        color:#60a5fa;
                    ">
                        ${escapeHtml(symbol)}
                    </div>

                    <div style="
                        font-size:0.8rem;
                        color:var(--text-muted);
                        margin:4px 0;
                    ">
                        Score:
                        ${fmtNum(
                    candidate.score
                )}
                    </div>

                    <div style="
                        font-size:0.78rem;
                        color:var(--text-muted);
                        margin-bottom:8px;
                    ">
                        ${reasons.length
                        ? escapeHtml(
                            reasons.join(
                                ", "
                            )
                        )
                        : "High momentum"
                    }
                    </div>

                    <button
                        class="
                            btn
                            btn-primary
                            btn-small
                        "
                        style="width:100%;"
                        onclick="quickAnalyze('${escapeHtml(
                        symbol
                    )}')"
                    >
                        Analyze Candidate
                    </button>
                `;

                container.appendChild(card);
            });
        })
        .catch(error => {
            console.error(
                "Screener error:",
                error
            );

            container.innerHTML = `
                <div style="
                    color:#fb7185;
                ">
                    Screener request failed.
                </div>
            `;
        });
}


function quickAnalyze(symbol) {
    const input =
        document.getElementById(
            "analysis-symbol"
        );

    if (input) {
        input.value =
            symbol;
    }

    const buttons =
        document.querySelectorAll(
            ".tab-btn"
        );

    switchTab(
        "analysis",
        buttons[0]
    );

    runAnalysis();
}


// ============================================================
// BACKTEST SIMULATOR
// ============================================================

function runBacktest() {
    const symbol =
        document.getElementById(
            "bt-symbol"
        )?.value
            .toUpperCase();

    const days =
        parseInt(
            document.getElementById(
                "bt-days"
            )?.value
        );

    const cash =
        parseFloat(
            document.getElementById(
                "bt-cash"
            )?.value
        );

    fetch("/api/backtest", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            symbol,
            days,
            initial_cash: cash
        })
    })
        .then(response => response.json())
        .then(data => {
            const results =
                document.getElementById(
                    "bt-results"
                );

            if (results) {
                results.style.display =
                    "flex";
            }

            const stats =
                data.summary ||
                data.stats ||
                data;

            const statsGrid =
                document.getElementById(
                    "bt-stats-grid"
                );

            if (statsGrid) {
                statsGrid.innerHTML = `
                    <div class="card" style="
                        text-align:center;
                    ">
                        <div style="
                            font-size:0.75rem;
                            color:var(--text-muted);
                        ">
                            TOTAL RETURN
                        </div>

                        <div style="
                            font-size:1.2rem;
                            font-weight:700;
                            color:${stats.total_return_pct >= 0
                        ? "#34d399"
                        : "#fb7185"
                    };
                        ">
                            ${fmtNum(
                        stats.total_return_pct
                    )}%
                        </div>
                    </div>

                    <div class="card" style="
                        text-align:center;
                    ">
                        <div style="
                            font-size:0.75rem;
                            color:var(--text-muted);
                        ">
                            WIN RATE
                        </div>

                        <div style="
                            font-size:1.2rem;
                            font-weight:700;
                        ">
                            ${fmtNum(
                        stats.win_rate_pct
                    )}%
                        </div>
                    </div>

                    <div class="card" style="
                        text-align:center;
                    ">
                        <div style="
                            font-size:0.75rem;
                            color:var(--text-muted);
                        ">
                            PROFIT FACTOR
                        </div>

                        <div style="
                            font-size:1.2rem;
                            font-weight:700;
                        ">
                            ${fmtNum(
                        stats.profit_factor
                    )}
                        </div>
                    </div>

                    <div class="card" style="
                        text-align:center;
                    ">
                        <div style="
                            font-size:0.75rem;
                            color:var(--text-muted);
                        ">
                            MAX DRAWDOWN
                        </div>

                        <div style="
                            font-size:1.2rem;
                            font-weight:700;
                            color:#fb7185;
                        ">
                            ${fmtNum(
                        stats.max_drawdown_pct
                    )}%
                        </div>
                    </div>

                    <div class="card" style="
                        text-align:center;
                    ">
                        <div style="
                            font-size:0.75rem;
                            color:var(--text-muted);
                        ">
                            SHARPE RATIO
                        </div>

                        <div style="
                            font-size:1.2rem;
                            font-weight:700;
                        ">
                            ${fmtNum(
                        stats.sharpe_ratio
                    )}
                        </div>
                    </div>
                `;
            }


            const curve =
                data.equity_curve ||
                [];

            const equityCanvas =
                document.getElementById(
                    "equityChart"
                );

            if (
                curve.length &&
                equityCanvas
            ) {
                const ctxEq =
                    equityCanvas.getContext(
                        "2d"
                    );

                if (ctxEq) {
                    if (equityChart) {
                        equityChart.destroy();
                    }

                    equityChart =
                        new Chart(
                            ctxEq,
                            {
                                type: "line",

                                data: {
                                    labels:
                                        curve.map(
                                            (_, index) =>
                                                `Day ${index + 1
                                                }`
                                        ),

                                    datasets: [
                                        {
                                            label:
                                                "Portfolio Equity ($)",

                                            data:
                                                curve,

                                            borderColor:
                                                "#10b981",

                                            borderWidth: 2,

                                            pointRadius: 0
                                        }
                                    ]
                                },

                                options: {
                                    responsive: true,

                                    maintainAspectRatio:
                                        false
                                }
                            }
                        );
                }
            }


            const tbody =
                document.querySelector(
                    "#bt-trades-table tbody"
                );

            if (tbody) {
                tbody.innerHTML = "";

                (
                    data.trades ||
                    []
                ).forEach(trade => {
                    const pnl =
                        parseFloat(
                            trade.pnl || 0
                        );

                    tbody.innerHTML += `
                        <tr>

                            <td>
                                ${escapeHtml(
                        trade.entry_date ||
                        "N/A"
                    )}
                            </td>

                            <td>
                                ${escapeHtml(
                        trade.exit_date ||
                        "N/A"
                    )}
                            </td>

                            <td style="
                                text-transform:uppercase;
                            ">
                                ${escapeHtml(
                        trade.side ||
                        "buy"
                    )}
                            </td>

                            <td>
                                ${fmtMoney(
                        trade.entry_price
                    )}
                            </td>

                            <td>
                                ${fmtMoney(
                        trade.exit_price
                    )}
                            </td>

                            <td style="
                                color:${pnl >= 0
                            ? "#34d399"
                            : "#fb7185"
                        };
                            ">
                                ${fmtMoney(pnl)}
                            </td>

                        </tr>
                    `;
                });
            }
        })
        .catch(error => {
            console.error(
                "Backtest error:",
                error
            );
        });
}


// ============================================================
// REFLECTIONS & REPORTS
// ============================================================

function generateReflection() {
    fetch("/api/history?limit=20")
        .then(response => response.json())
        .then(history => {
            return fetch(
                "/api/reflection",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        trades: history
                    })
                }
            );
        })
        .then(response => response.json())
        .then(data => {
            const output =
                document.getElementById(
                    "reflection-output"
                );

            if (output) {
                output.textContent =
                    data.reflection ||
                    "No reflection insights available.";
            }
        })
        .catch(error => {
            console.error(
                "Reflection error:",
                error
            );
        });
}


function loadDailyReport() {
    fetch("/api/report/daily")
        .then(response => response.json())
        .then(data => {
            const output =
                document.getElementById(
                    "daily-report-output"
                );

            if (!output) {
                return;
            }

            output.innerHTML = `
                <div style="
                    display:flex;
                    gap:20px;
                ">

                    <div>
                        Analyses Run Today:
                        <strong>
                            ${data.total_analyses ||
                0
                }
                        </strong>
                    </div>

                    <div>
                        Orders Submitted Today:
                        <strong>
                            ${data.total_orders ||
                0
                }
                        </strong>
                    </div>

                    <div>
                        Win Rate Estimate:
                        <strong>
                            ${fmtNum(
                    data.estimated_win_rate
                )}%
                        </strong>
                    </div>

                </div>
            `;
        })
        .catch(error => {
            console.error(
                "Daily report error:",
                error
            );
        });
}


// ============================================================
// SEMANTIC VECTOR SEARCH
// ============================================================

function runVectorSearch() {
    const input =
        document.getElementById(
            "search-query"
        );

    const query =
        input?.value.trim();

    if (!query) {
        return;
    }

    fetch("/api/search", {
        method: "POST",
        headers: {
            "Content-Type":
                "application/json"
        },
        body: JSON.stringify({
            query,
            top_k: 5
        })
    })
        .then(response => response.json())
        .then(data => {
            const container =
                document.getElementById(
                    "search-results"
                );

            if (!container) {
                return;
            }

            container.innerHTML = "";

            (
                data.results ||
                []
            ).forEach(result => {
                const card =
                    document.createElement(
                        "div"
                    );

                card.className =
                    "card";

                card.innerHTML = `
                    <div style="
                        display:flex;
                        justify-content:space-between;
                        margin-bottom:4px;
                    ">

                        <strong style="
                            color:#60a5fa;
                        ">
                            ${escapeHtml(
                    result.symbol ||
                    "Note"
                )}
                        </strong>

                        <span style="
                            font-size:0.8rem;
                            color:var(--text-muted);
                        ">
                            Similarity Score:
                            ${fmtNum(
                    result.score
                )}
                        </span>

                    </div>

                    <div style="
                        font-size:0.85rem;
                        color:var(--text-main);
                    ">
                        ${escapeHtml(
                    result.text ||
                    result.reason ||
                    ""
                )}
                    </div>
                `;

                container.appendChild(card);
            });
        })
        .catch(error => {
            console.error(
                "Vector search error:",
                error
            );
        });
}


// ============================================================
// HISTORY LEDGER
// ============================================================

function loadHistory() {
    fetch("/api/history?limit=50")
        .then(response => response.json())
        .then(data => {
            const tbody =
                document.querySelector(
                    "#history-table tbody"
                );

            if (!tbody) {
                return;
            }

            tbody.innerHTML = "";

            (
                data || []
            ).forEach(item => {
                const timeStr =
                    new Date(
                        item.timestamp ||
                        Date.now()
                    ).toLocaleTimeString();

                const type =
                    item.type ||
                    (
                        item.order_id
                            ? "order"
                            : "analysis"
                    );

                const action =
                    (
                        item.action ||
                        item.side ||
                        "hold"
                    ).toLowerCase();

                const confidence =
                    item.confidence
                        ? (
                            item.confidence *
                            100
                        ).toFixed(0) + "%"
                        : "N/A";

                tbody.innerHTML += `
                    <tr>

                        <td>
                            ${timeStr}
                        </td>

                        <td>
                            <span
                                class="status-pill"
                                style="
                                    padding:2px 8px;
                                    font-size:0.75rem;
                                "
                            >
                                ${escapeHtml(
                    type.toUpperCase()
                )}
                            </span>
                        </td>

                        <td>
                            <strong>
                                ${escapeHtml(
                    item.symbol ||
                    "N/A"
                )}
                            </strong>
                        </td>

                        <td>
                            <span
                                class="
                                    status-pill
                                    badge-${escapeHtml(
                    action
                )}
                                "
                                style="
                                    padding:2px 8px;
                                    font-size:0.75rem;
                                "
                            >
                                ${escapeHtml(
                    action.toUpperCase()
                )}
                            </span>
                        </td>

                        <td>
                            ${confidence}
                        </td>

                        <td style="
                            font-size:0.8rem;
                            color:var(--text-muted);
                        ">
                            ${escapeHtml(
                    item.reason ||
                    "N/A"
                )}
                        </td>

                    </tr>
                `;
            });
        })
        .catch(error => {
            console.error(
                "History error:",
                error
            );
        });


    fetch("/api/history/stats")
        .then(response => response.json())
        .then(stats => {
            const bar =
                document.getElementById(
                    "history-stats-bar"
                );

            if (!bar) {
                return;
            }

            bar.textContent =
                `Total Recorded Entries: ${stats.total_entries || 0
                } | Buy Orders: ${stats.buy_orders || 0
                } | Sell Orders: ${stats.sell_orders || 0
                } | Total Analyses: ${stats.total_analyses || 0
                }`;
        })
        .catch(error => {
            console.error(
                "History stats error:",
                error
            );
        });
}


// ============================================================
// REAL-TIME TELEMETRY POLLING
// ============================================================

function pollMessages() {
    fetch(
        `/api/messages?since=${commIndex}`
    )
        .then(response => response.json())
        .then(data => {
            const log =
                document.getElementById(
                    "comm-log"
                );

            if (!log) {
                return;
            }

            (
                data.messages ||
                []
            ).forEach(message => {
                const entry =
                    document.createElement(
                        "div"
                    );

                const fromClass =
                    "from-" +
                    (
                        message.from ||
                        ""
                    )
                        .replace(
                            /_/g,
                            "-"
                        )
                        .toLowerCase();

                entry.className =
                    `comm-entry ${fromClass}`;

                entry.innerHTML = `
                    <div class="comm-header">

                        <span>
                            <strong>
                                ${escapeHtml(
                    message.from
                )}
                            </strong>

                            &rarr;

                            ${escapeHtml(
                    message.to
                )}
                        </span>

                        <span>
                            ${new Date(
                    message.timestamp ||
                    Date.now()
                ).toLocaleTimeString()}
                        </span>

                    </div>

                    <div class="comm-msg">
                        ${escapeHtml(
                    message.message
                )}
                    </div>
                `;

                log.appendChild(entry);
            });

            if (
                data.messages &&
                data.messages.length > 0
            ) {
                log.scrollTop =
                    log.scrollHeight;

                renderGroupChatFeed(false);
            }

            if (
                data.next_index !== undefined
            ) {
                commIndex =
                    data.next_index;
            }
        })
        .catch(() => { })
        .finally(() => {
            setTimeout(
                pollMessages,
                2000
            );
        });
}


// ============================================================
// PORTFOLIO VISUALIZATION
// ============================================================

// IMPORTANT:
// portfolioChart is declared ONCE at the top of this file.
// Do NOT redeclare it here.

const portfolioChartState = {
    range: "1D",
    mode: "return",
    symbols: []
};

const portfolioChartModeLabels = {
    return: "% change from starting date",
    normalized: "Normalized price (start = 100)",
    price: "Actual stock price",
    value: "Portfolio value",
    pnl: "Dollar profit/loss",
    marketcap: "Market-cap-adjusted price"
};

let portfolioCurrentRange = "1D";
let portfolioSelectedSymbols = new Set(["ALL"]);
let portfolioRequestInProgress = false;
let portfolioLastData = null;
let portfolioChartRequestToken = 0;

function setPortfolioRange(range, button) {
    setPortfolioChartRange(range, button);
}

function togglePortfolioSymbol(symbol, button) {
    const normalizedSymbol = String(symbol ?? "").trim().toUpperCase();

    if (!normalizedSymbol) {
        return;
    }

    if (normalizedSymbol === "ALL") {
        portfolioSelectedSymbols = new Set(["ALL"]);

        document.querySelectorAll(".portfolio-symbol-btn").forEach(btn => {
            const isAll = btn.dataset.symbol === "ALL";
            btn.classList.toggle("active", isAll);
            btn.classList.toggle("btn-primary", isAll);
            btn.classList.toggle("btn-secondary", !isAll);
        });

        loadPortfolioChart();
        return;
    }

    if (portfolioSelectedSymbols.has("ALL")) {
        portfolioSelectedSymbols.delete("ALL");
    }

    if (portfolioSelectedSymbols.has(normalizedSymbol)) {
        portfolioSelectedSymbols.delete(normalizedSymbol);
    }
    else {
        portfolioSelectedSymbols.add(normalizedSymbol);
    }

    if (portfolioSelectedSymbols.size === 0) {
        portfolioSelectedSymbols = new Set(["ALL"]);
    }

    document.querySelectorAll(".portfolio-symbol-btn").forEach(btn => {
        const symbolValue = String(btn.dataset.symbol || "").toUpperCase();
        const isActive = portfolioSelectedSymbols.has(symbolValue) || (
            portfolioSelectedSymbols.size === 1 && portfolioSelectedSymbols.has("ALL") && symbolValue === "ALL"
        );

        btn.classList.toggle("active", isActive);
        btn.classList.toggle("btn-primary", isActive);
        btn.classList.toggle("btn-secondary", !isActive);
    });

    loadPortfolioChart();
}

function updatePortfolioSymbolControls(symbols) {
    const container = document.getElementById("portfolio-symbol-controls");

    if (!container) {
        return;
    }

    const normalizedSymbols = Array.from(
        new Set(
            (Array.isArray(symbols) ? symbols : [])
                .map(symbol => String(symbol).trim().toUpperCase())
                .filter(Boolean)
        )
    ).sort();

    const previousSelection = new Set(portfolioSelectedSymbols);
    container.innerHTML = "";

    const label = document.createElement("span");
    label.style.fontSize = "0.78rem";
    label.style.color = "var(--text-muted)";
    label.style.marginRight = "4px";
    label.textContent = "Symbols:";
    container.appendChild(label);

    const allButton = document.createElement("button");
    allButton.type = "button";
    allButton.className = "btn btn-secondary btn-small portfolio-symbol-btn";
    allButton.dataset.symbol = "ALL";
    allButton.textContent = "All";
    allButton.onclick = () => togglePortfolioSymbol("ALL", allButton);

    if (previousSelection.has("ALL") || previousSelection.size === 0) {
        allButton.classList.add("active");
        allButton.classList.remove("btn-secondary");
        allButton.classList.add("btn-primary");
        portfolioSelectedSymbols = new Set(["ALL"]);
    }

    container.appendChild(allButton);

    normalizedSymbols.forEach(symbol => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-secondary btn-small portfolio-symbol-btn";
        button.dataset.symbol = symbol;
        button.textContent = symbol;
        button.onclick = () => togglePortfolioSymbol(symbol, button);

        if (previousSelection.has(symbol) && !previousSelection.has("ALL")) {
            button.classList.add("active");
            button.classList.remove("btn-secondary");
            button.classList.add("btn-primary");
        }

        container.appendChild(button);
    });
}

async function loadPortfolioPerformance() {
    return loadPortfolioChart();
}

function initializePortfolioPerformance() {
    return initializePortfolioVisualization();
}


function formatPortfolioSummaryCurrency(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
        return "—";
    }

    return new Intl.NumberFormat("en-US", {
        style: "currency",
        currency: "USD",
        maximumFractionDigits: 2
    }).format(Number(value));
}


function formatPortfolioSummaryPercent(value) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) {
        return "—";
    }

    const number = Number(value);

    return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}


function syncPortfolioChartSymbolsFromPage() {
    if (typeof portfolioSelectedSymbols === "undefined") {
        return;
    }

    if (
        portfolioSelectedSymbols.has("ALL") ||
        portfolioSelectedSymbols.size === 0
    ) {
        portfolioChartState.symbols = [];
        return;
    }

    portfolioChartState.symbols = Array.from(portfolioSelectedSymbols)
        .map(symbol => String(symbol).trim().toUpperCase())
        .filter(Boolean);
}


function updatePortfolioChartSummary(data) {
    const currentValueElement =
        document.getElementById("portfolio-current-value");

    const returnElement =
        document.getElementById("portfolio-period-return");

    if (!currentValueElement && !returnElement) {
        return;
    }

    let currentValue = Number(data?.current_value);
    let periodReturn = Number(data?.period_return_pct);

    const portfolioPoints = Array.isArray(data?.portfolio)
        ? data.portfolio
        : [];

    if (!Number.isFinite(currentValue) && portfolioPoints.length > 0) {
        for (let index = portfolioPoints.length - 1; index >= 0; index -= 1) {
            const point = portfolioPoints[index];

            if (!point || typeof point !== "object") {
                continue;
            }

            const equity = Number(
                point.equity ?? point.value
            );

            if (Number.isFinite(equity)) {
                currentValue = equity;
                break;
            }
        }
    }

    if (!Number.isFinite(periodReturn) && portfolioPoints.length > 0) {
        for (let index = portfolioPoints.length - 1; index >= 0; index -= 1) {
            const point = portfolioPoints[index];

            if (!point || typeof point !== "object") {
                continue;
            }

            const returnPct = Number(point.return_pct);

            if (Number.isFinite(returnPct)) {
                periodReturn = returnPct;
                break;
            }
        }
    }

    if (currentValueElement) {
        currentValueElement.textContent =
            formatPortfolioSummaryCurrency(currentValue);
    }

    if (returnElement) {
        returnElement.textContent =
            formatPortfolioSummaryPercent(periodReturn);

        returnElement.style.color =
            periodReturn >= 0
                ? "#34d399"
                : "#f87171";
    }
}


// ============================================================
// LOAD PORTFOLIO CHART
// ============================================================

async function loadPortfolioChart() {
    const canvas =
        document.getElementById(
            "portfolioChart"
        );

    // The portfolio tab may not be mounted yet.
    if (!canvas) {
        console.warn(
            "portfolioChart canvas not found. " +
            "Make sure the portfolio chart HTML contains " +
            '<canvas id="portfolioChart"></canvas>.'
        );

        return;
    }

    const activeRange =
        String(
            portfolioChartState?.range ||
            (typeof portfolioCurrentRange !== "undefined"
                ? portfolioCurrentRange
                : "1D")
        )
            .trim()
            .toUpperCase();

    if (typeof portfolioCurrentRange !== "undefined") {
        portfolioCurrentRange = activeRange;
    }

    portfolioChartState.range = activeRange;

    syncPortfolioChartSymbolsFromPage();

    const selectedRangeEl =
        document.getElementById(
            "portfolio-selected-range"
        );

    if (selectedRangeEl) {
        selectedRangeEl.textContent =
            activeRange === "ALL"
                ? "All"
                : activeRange;
    }

    if (portfolioRequestInProgress) {
        return;
    }

    const requestId = ++portfolioChartRequestToken;
    portfolioRequestInProgress = true;

    try {
        showPortfolioChartState("loading");

        const params =
            new URLSearchParams();

        params.set(
            "range",
            activeRange
        );

        params.set(
            "mode",
            portfolioChartState.mode
        );

        if (
            portfolioChartState.symbols.length >
            0
        ) {
            params.set(
                "symbols",
                portfolioChartState.symbols.join(",")
            );
        }

        const response =
            await fetch(
                `/api/portfolio_chart?${params.toString()}`,
                {
                    method: "GET",

                    headers: {
                        "Accept":
                            "application/json"
                    }
                }
            );

        let data;

        try {
            data =
                await response.json();
        }
        catch (jsonError) {
            throw new Error(
                `Server returned invalid JSON ` +
                `(HTTP ${response.status})`
            );
        }

        if (requestId !== portfolioChartRequestToken) {
            return;
        }

        if (data.status === "not_configured") {
            showPortfolioChartError(
                data.error ||
                "Add Alpaca credentials to load portfolio performance."
            );
            updatePortfolioChartSummary(data);
            return;
        }

        if (
            !response.ok ||
            data.status !== "ok"
        ) {
            throw new Error(
                data.error ||
                `Failed to load portfolio chart ` +
                `(HTTP ${response.status})`
            );
        }

        renderPortfolioChart(data);

        if (
            Array.isArray(data.symbols) &&
            data.symbols.length > 0 &&
            typeof updatePortfolioSymbolControls === "function"
        ) {
            updatePortfolioSymbolControls(data.symbols);
        }

        updatePortfolioChartSummary(data);
    }
    catch (error) {
        if (requestId !== portfolioChartRequestToken) {
            return;
        }

        console.error(
            "Portfolio chart error:",
            error
        );

        showPortfolioChartError(
            error.message ||
            "Unable to load portfolio chart."
        );
    }
    finally {
        if (requestId === portfolioChartRequestToken) {
            portfolioRequestInProgress = false;
        }
    }
}


// ============================================================
// RENDER PORTFOLIO CHART
// ============================================================

function renderPortfolioChart(data) {
    const canvas =
        document.getElementById(
            "portfolioChart"
        );

    if (!canvas) {
        console.warn(
            "Cannot render portfolio chart: " +
            "canvas #portfolioChart does not exist."
        );

        return;
    }

    if (
        typeof Chart ===
        "undefined"
    ) {
        console.error(
            "Chart.js is not loaded. " +
            "Load Chart.js before dashboard.js."
        );

        showPortfolioChartError(
            "Chart.js is not loaded."
        );

        return;
    }

    const ctx =
        canvas.getContext("2d");

    if (!ctx) {
        showPortfolioChartError(
            "Unable to initialize the chart canvas."
        );

        return;
    }

    if (portfolioChartInstance) {
        portfolioChartInstance.destroy();
        portfolioChartInstance = null;
    }

    const datasets = [];
    const chartMode = String(data?.mode || portfolioChartState.mode || "return").toLowerCase();


    // --------------------------------------------------------
    // Portfolio line
    // --------------------------------------------------------

    if (
        Array.isArray(
            data.portfolio
        ) &&
        data.portfolio.length > 0
    ) {
        const portfolioData =
            data.portfolio
                .filter(point =>
                    point &&
                    point.timestamp &&
                    point.value !== null &&
                    point.value !== undefined
                )
                .map(point => ({
                    x: point.timestamp,
                    y: Number(point.value)
                }))
                .filter(point =>
                    Number.isFinite(point.y)
                );

        if (portfolioData.length > 0) {
            datasets.push({
                label:
                    chartMode === "value"
                        ? "Portfolio Value"
                        : chartMode === "price"
                            ? "Portfolio Price"
                            : chartMode === "pnl"
                                ? "Portfolio P/L"
                                : chartMode === "normalized"
                                    ? "Normalized Portfolio"
                                    : chartMode === "marketcap"
                                        ? "Market-cap-adjusted Portfolio"
                                        : "Portfolio Return",

                data:
                    portfolioData,

                borderColor:
                    "#4ade80",

                backgroundColor:
                    "rgba(74, 222, 128, 0.10)",

                borderWidth: 2,

                pointRadius: 0,

                pointHoverRadius: 4,

                tension: 0.25,

                fill: true,

                spanGaps: true
            });
        }
    }


    // --------------------------------------------------------
    // Position lines
    // --------------------------------------------------------

    if (
        Array.isArray(
            data.positions
        ) &&
        data.positions.length > 0
    ) {
        const colors = [
            "#60a5fa",
            "#f59e0b",
            "#a78bfa",
            "#f472b6",
            "#22d3ee",
            "#fb7185",
            "#34d399",
            "#facc15"
        ];

        data.positions.forEach(
            (position, index) => {
                if (
                    !position ||
                    !Array.isArray(
                        position.data
                    ) ||
                    position.data.length === 0
                ) {
                    return;
                }

                const lineData =
                    position.data
                        .filter(point =>
                            point &&
                            point.timestamp &&
                            point.value !== null &&
                            point.value !== undefined
                        )
                        .map(point => ({
                            x: point.timestamp,
                            y: Number(point.value)
                        }))
                        .filter(point =>
                            Number.isFinite(
                                point.y
                            )
                        );

                if (!lineData.length) {
                    return;
                }

                datasets.push({
                    label:
                        position.symbol ||
                        "Position",

                    data:
                        lineData,

                    borderColor:
                        colors[
                        index %
                        colors.length
                        ],

                    borderWidth: 1.5,

                    pointRadius: 0,

                    pointHoverRadius: 4,

                    tension: 0.2,

                    spanGaps: true,

                    fill: false
                });
            }
        );
    }


    // --------------------------------------------------------
    // Trade markers
    // --------------------------------------------------------

    const allTrades =
        Array.isArray(data.trades)
            ? data.trades
            : [];

    const buyTrades =
        allTrades.filter(
            trade =>
                String(
                    trade.side || ""
                ).toUpperCase() ===
                "BUY"
        );

    const sellTrades =
        allTrades.filter(
            trade =>
                String(
                    trade.side || ""
                ).toUpperCase() ===
                "SELL"
        );


    if (buyTrades.length > 0) {
        const buyData =
            buyTrades
                .filter(trade =>
                    trade.timestamp &&
                    trade.value !== null &&
                    trade.value !== undefined
                )
                .map(trade => ({
                    x: trade.timestamp,
                    y: Number(trade.value)
                }))
                .filter(point =>
                    Number.isFinite(
                        point.y
                    )
                );

        if (buyData.length > 0) {
            datasets.push({
                label: "Buy",

                data:
                    buyData,

                type: "scatter",

                backgroundColor:
                    "#22c55e",

                borderColor:
                    "#ffffff",

                borderWidth: 1,

                pointRadius: 6,

                pointHoverRadius: 9
            });
        }
    }


    if (sellTrades.length > 0) {
        const sellData =
            sellTrades
                .filter(trade =>
                    trade.timestamp &&
                    trade.value !== null &&
                    trade.value !== undefined
                )
                .map(trade => ({
                    x: trade.timestamp,
                    y: Number(trade.value)
                }))
                .filter(point =>
                    Number.isFinite(
                        point.y
                    )
                );

        if (sellData.length > 0) {
            datasets.push({
                label: "Sell",

                data:
                    sellData,

                type: "scatter",

                backgroundColor:
                    "#ef4444",

                borderColor:
                    "#ffffff",

                borderWidth: 1,

                pointRadius: 6,

                pointHoverRadius: 9
            });
        }
    }


    // --------------------------------------------------------
    // No data
    // --------------------------------------------------------

    if (datasets.length === 0) {
        showPortfolioChartEmpty();
        return;
    }

    if (typeof showPortfolioChartState === "function") {
        showPortfolioChartState("ready");
    }


    // --------------------------------------------------------
    // Remove previous messages
    // --------------------------------------------------------

    const container =
        document.getElementById(
            "portfolioChartContainer"
        );

    if (container) {
        const message =
            container.querySelector(
                ".portfolio-chart-message"
            );

        if (message) {
            message.remove();
        }

        const errorBox =
            container.querySelector(
                ".portfolio-chart-error"
            );

        if (errorBox) {
            errorBox.remove();
        }

        canvas.style.display =
            "block";
    }


    // --------------------------------------------------------
    // Chart configuration
    // --------------------------------------------------------

    portfolioChartInstance =
        new Chart(
            ctx,
            {
                type: "line",

                data: {
                    datasets
                },

                options: {
                    responsive: true,

                    maintainAspectRatio:
                        false,

                    animation: {
                        duration: 0,
                        active: {
                            duration: 0
                        }
                    },

                    interaction: {
                        mode: "nearest",
                        intersect: false
                    },

                    plugins: {
                        legend: {
                            display: false,

                            labels: {
                                color:
                                    "#d1d5db",

                                usePointStyle:
                                    true,

                                padding: 14,

                                font: {
                                    family:
                                        "Inter, sans-serif",

                                    size: 11
                                }
                            }
                        },

                        tooltip: {
                            callbacks: {
                                label:
                                    function (
                                        context
                                    ) {
                                        const value =
                                            context
                                                .parsed
                                                .y;

                                        if (
                                            value ===
                                            null ||
                                            value ===
                                            undefined ||
                                            Number.isNaN(
                                                value
                                            )
                                        ) {
                                            return "";
                                        }

                                        const label =
                                            context
                                                .dataset
                                                .label ||
                                            "Value";

                                        if (
                                            chartMode === "return" &&
                                            label !== "Buy" &&
                                            label !== "Sell"
                                        ) {
                                            const signedValue =
                                                Number(value) >= 0
                                                    ? `+${Number(value).toFixed(2)}`
                                                    : Number(value).toFixed(2);

                                            return `${label}: ${signedValue}%`;
                                        }

                                        if (
                                            chartMode === "value" ||
                                            chartMode === "pnl"
                                        ) {
                                            return (
                                                `${label}: ` +
                                                formatPortfolioSummaryCurrency(value)
                                            );
                                        }

                                        if (
                                            chartMode === "price" ||
                                            chartMode === "normalized" ||
                                            chartMode === "marketcap"
                                        ) {
                                            return (
                                                `${label}: ${Number(value).toFixed(2)}`
                                            );
                                        }

                                        return (
                                            `${label}: ` +
                                            `${Number(
                                                value
                                            ).toFixed(
                                                2
                                            )}`
                                        );
                                    }
                            }
                        }
                    },

                    scales: {
                        x: {
                            type: "time",

                            ticks: {
                                color:
                                    "#9ca3af",

                                maxRotation: 0,

                                autoSkip: true,

                                maxTicksLimit: 8
                            },

                            grid: {
                                color:
                                    "rgba(255,255,255,0.05)"
                            }
                        },

                        y: {
                            ticks: {
                                color:
                                    "#9ca3af",

                                callback:
                                    function (
                                        value
                                    ) {
                                        if (
                                            chartMode === "return"
                                        ) {
                                            const signedValue =
                                                Number(value) >= 0
                                                    ? `+${Number(value).toFixed(1)}`
                                                    : Number(value).toFixed(1);

                                            return `${signedValue}%`;
                                        }

                                        if (
                                            chartMode === "value" ||
                                            chartMode === "pnl"
                                        ) {
                                            return formatPortfolioSummaryCurrency(value);
                                        }

                                        if (chartMode === "price") {
                                            return Number(value).toLocaleString(undefined, {
                                                maximumFractionDigits: 2
                                            });
                                        }

                                        return Number(value).toLocaleString(undefined, {
                                            maximumFractionDigits: 2
                                        });
                                    }
                            },

                            grid: {
                                color:
                                    "rgba(255,255,255,0.05)"
                            }
                        }
                    }
                }
            }
        );
}


// ============================================================
// PORTFOLIO CHART STATE
// ============================================================

function showPortfolioChartState(state) {
    const normalizedState = String(state || "ready").toLowerCase();

    const loadingState =
        document.getElementById(
            "portfolio-chart-loading"
        );

    const emptyState =
        document.getElementById(
            "portfolio-chart-empty"
        );

    const errorState =
        document.getElementById(
            "portfolio-chart-error"
        );

    const errorMessage =
        document.getElementById(
            "portfolio-chart-error-message"
        );

    const canvas =
        document.getElementById(
            "portfolioChart"
        );

    if (loadingState) {
        loadingState.style.display =
            normalizedState === "loading"
                ? "flex"
                : "none";
    }

    if (emptyState) {
        emptyState.style.display =
            normalizedState === "empty"
                ? "flex"
                : "none";
    }

    if (errorState) {
        errorState.style.display =
            normalizedState === "error"
                ? "flex"
                : "none";
    }

    if (errorMessage && normalizedState !== "error") {
        errorMessage.textContent =
            "Please try refreshing the chart.";
    }

    if (canvas) {
        canvas.style.display =
            normalizedState === "ready"
                ? "block"
                : "none";
    }
}

function showPortfolioChartLoading() {
    showPortfolioChartState("loading");
}

function showPortfolioChartEmpty() {
    showPortfolioChartState("empty");
}

function showPortfolioChartError(message) {
    const errorMessage =
        document.getElementById(
            "portfolio-chart-error-message"
        );

    if (errorMessage) {
        errorMessage.textContent =
            message ||
            "Unable to load portfolio chart.";
    }

    showPortfolioChartState("error");
}


// ============================================================
// PORTFOLIO RANGE
// ============================================================

function setPortfolioChartRange(range, button) {
    if (!range) {
        return;
    }

    const normalizedRange =
        String(range)
            .trim()
            .toUpperCase();

    const validRanges = ['1D', '1W', '1M', '2M', '3M', '6M', '1Y', 'ALL'];

    if (!validRanges.includes(normalizedRange)) {
        return;
    }

    portfolioChartState.range = normalizedRange;

    if (typeof portfolioCurrentRange !== "undefined") {
        portfolioCurrentRange = normalizedRange;
    }

    document
        .querySelectorAll(
            "[data-portfolio-range], .portfolio-range-btn"
        )
        .forEach(btn => {
            const btnRange = String(
                btn.dataset.portfolioRange || btn.textContent || ""
            )
                .trim()
                .toUpperCase();

            const isActive = btnRange === normalizedRange;

            btn.classList.toggle("active", isActive);
            btn.classList.toggle("btn-primary", isActive);
            btn.classList.toggle("btn-secondary", !isActive);
        });

    if (button) {
        button.classList.add("active");
        button.classList.remove("btn-secondary");
        button.classList.add("btn-primary");
    }

    const selectedRange =
        document.getElementById(
            "portfolio-selected-range"
        );

    if (selectedRange) {
        selectedRange.textContent =
            normalizedRange === "ALL"
                ? "All"
                : normalizedRange;
    }

    loadPortfolioChart();
}


// ============================================================
// PORTFOLIO MODE
// ============================================================

function setPortfolioChartMode(mode) {
    const validModes = [
        "return",
        "normalized",
        "price",
        "value",
        "pnl",
        "marketcap"
    ];

    const normalizedMode = String(mode || "return").trim().toLowerCase();

    if (!validModes.includes(normalizedMode)) {
        return;
    }

    portfolioChartState.mode = normalizedMode;

    document
        .querySelectorAll(
            "[data-portfolio-mode]"
        )
        .forEach(button => {
            const isActive =
                (button.dataset.portfolioMode || "")
                    .trim()
                    .toLowerCase() === normalizedMode;

            button.classList.toggle("active", isActive);
            button.classList.toggle("btn-primary", isActive);
            button.classList.toggle("btn-secondary", !isActive);
        });

    loadPortfolioChart();
}

// ============================================================
// PORTFOLIO CHART AUTO REFRESH
// ============================================================

let portfolioChartRefreshTimer = null;
let portfolioChartLoading = false;

function schedulePortfolioChartRefresh(delay = 10000) {
    if (portfolioChartRefreshTimer) {
        clearTimeout(portfolioChartRefreshTimer);
    }

    portfolioChartRefreshTimer = setTimeout(
        refreshPortfolioChart,
        delay
    );
}

async function refreshPortfolioChart() {
    if (portfolioChartLoading) {
        schedulePortfolioChartRefresh(2000);
        return;
    }

    portfolioChartLoading = true;

    try {
        await loadPortfolioChart();
    }
    finally {
        portfolioChartLoading = false;
        schedulePortfolioChartRefresh(10000);
    }
}


// ============================================================
// INITIALIZE PORTFOLIO VISUALIZATION
// ============================================================

function initializePortfolioVisualization() {
    document
        .querySelectorAll(
            "[data-portfolio-range]"
        )
        .forEach(button => {
            if (button.dataset.portfolioRangeBound === "true") {
                return;
            }

            button.dataset.portfolioRangeBound = "true";
            button.addEventListener(
                "click",
                () => {
                    setPortfolioChartRange(
                        button.dataset
                            .portfolioRange
                    );
                }
            );
        });

    document
        .querySelectorAll(
            "[data-portfolio-mode]"
        )
        .forEach(button => {
            if (button.dataset.portfolioModeBound === "true") {
                return;
            }

            button.dataset.portfolioModeBound = "true";
            button.addEventListener(
                "click",
                () => {
                    setPortfolioChartMode(
                        button.dataset
                            .portfolioMode
                    );
                }
            );
        });

    const canvas =
        document.getElementById(
            "portfolioChart"
        );

    if (canvas) {
        loadPortfolioChart();
    }
    else {
        console.warn(
            "Portfolio visualization initialized, " +
            "but #portfolioChart is not present in the page."
        );
    }
}


// ============================================================
// DOM READY
// ============================================================

document.addEventListener(
    "DOMContentLoaded",
    () => {
        fetchDiagnostics();
        refreshAccount();
        fetchSessions();
        loadHistory();
        pollMessages();
        initializePortfolioVisualization();
        fetchAutonomousStatus();
        fetchErrors();
    }
);


// ============================================================
// COMMUNICATION LOG
// ============================================================

function clearCommLog() {
    const log =
        document.getElementById(
            "comm-log"
        );

    if (log) {
        log.innerHTML = "";
    }
}