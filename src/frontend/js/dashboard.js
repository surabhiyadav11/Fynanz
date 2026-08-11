let allTransactions = [];
let currentPeriod = "week";
let categoryChart = null;
let trendChart = null;
let sortColumn = "date";
let sortDirection = "desc";
let userBadges = [];

document.addEventListener("DOMContentLoaded", () => {
    const today = new Date().toISOString().split("T")[0];
    const dateInput = document.getElementById("expenseDate");
    if (dateInput) {
        dateInput.value = today;
    }

    setupPeriodTabs();
    setupCategoryFilter();
    setupSearchInput();
    setupTableSort();
    setupPredictionsButton();
    setupBadgesToggle();

    loadDashboard();
    loadUserInfo();
    loadStreak();
    loadBadges();
});

// Handle logout
document.getElementById("logoutBtn").addEventListener("click", (e) => {
    e.preventDefault();
    logout();
});

// Handle add expense form
document.getElementById("addExpenseForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const amount = document.getElementById("amount").value;
    const description = document.getElementById("description").value;
    const category = document.getElementById("category").value;
    const expenseDate = document.getElementById("expenseDate").value;

    try {
        const result = await apiCall("/transactions", {
            method: "POST",
            body: JSON.stringify({
                amount: parseFloat(amount),
                description: description,
                category: category || null,
                currency: "INR",
                transaction_date: expenseDate,
            }),
        });

        const detectedCategory = result.category || category || "Other";
        showAlert(`Expense added! Category: ${detectedCategory}`, "success");

        document.getElementById("addExpenseForm").reset();
        document.getElementById("expenseDate").value = new Date().toISOString().split("T")[0];

        loadDashboard();
        loadBadges();
    } catch (error) {
        const errorMsg = error.message || error.detail || JSON.stringify(error);
        showAlert(errorMsg, "error");
    }
});

// Setup period tabs
function setupPeriodTabs() {
    const tabs = document.querySelectorAll(".tab-btn");
    tabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            tabs.forEach((t) => t.classList.remove("active"));
            tab.classList.add("active");

            currentPeriod = tab.dataset.period;
            updateDashboardForPeriod();
        });
    });
}

// Setup category filter
function setupCategoryFilter() {
    const filter = document.getElementById("categoryFilter");
    filter.addEventListener("change", () => {
        displayTransactions(allTransactions);
    });
}

// Setup search input
function setupSearchInput() {
    const searchInput = document.getElementById("searchInput");
    searchInput.addEventListener("input", () => {
        displayTransactions(allTransactions);
    });
}

// Setup table sorting
function setupTableSort() {
    const headers = document.querySelectorAll("#transactionsTable th.sortable");
    headers.forEach((header) => {
        header.addEventListener("click", () => {
            const column = header.dataset.column;
            if (sortColumn === column) {
                sortDirection = sortDirection === "asc" ? "desc" : "asc";
            } else {
                sortColumn = column;
                sortDirection = "desc";
            }
            updateSortIndicators();
            displayTransactions(allTransactions);
        });
    });
}

// Update sort indicators
function updateSortIndicators() {
    const headers = document.querySelectorAll("#transactionsTable th.sortable");
    headers.forEach((header) => {
        header.classList.remove("sort-asc", "sort-desc");
        if (header.dataset.column === sortColumn) {
            header.classList.add(sortDirection === "asc" ? "sort-asc" : "sort-desc");
        }
    });
}

// Setup predictions button
function setupPredictionsButton() {
    const btn = document.getElementById("getPredictionsBtn");
    btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "Loading...";
        await loadPredictions();
        btn.disabled = false;
        btn.textContent = "Refresh Predictions";
    });
}

// Load all dashboard data
async function loadDashboard() {
    try {
        const transactionsResult = await apiCall("/transactions?limit=200", {
            method: "GET",
        });

        allTransactions = transactionsResult.transactions || [];
        updateDashboardForPeriod();

        loadPredictions();
    } catch (error) {
        showAlert("Error loading dashboard", "error");
    }
}

// Update dashboard based on selected period
function updateDashboardForPeriod() {
    const filtered = filterTransactionsByPeriod(allTransactions, currentPeriod);

    const total = filtered.reduce((sum, tx) => sum + (parseFloat(tx.amount) || 0), 0);
    const count = filtered.length;

    let days = 7;
    if (currentPeriod === "month") days = 30;
    if (currentPeriod === "all") days = Math.max(1, getDaysSinceFirstTransaction(allTransactions));

    const average = count > 0 ? total / days : 0;

    document.getElementById("totalSpent").textContent = formatCurrency(total);
    document.getElementById("transactionCount").textContent = count;
    document.getElementById("dailyAverage").textContent = formatCurrency(average);

    updateCategoryChart(filtered);
    updateTrendChart(filtered, currentPeriod);

    displayTransactions(allTransactions);
}

// Filter transactions by period
function filterTransactionsByPeriod(transactions, period) {
    if (period === "all") return transactions;

    const now = new Date();
    const cutoff = new Date();

    if (period === "week") {
        cutoff.setDate(now.getDate() - 7);
    } else if (period === "month") {
        cutoff.setDate(now.getDate() - 30);
    }

    return transactions.filter((tx) => {
        const txDate = new Date(tx.transaction_date || tx.created_at);
        return txDate >= cutoff;
    });
}

// Get days since first transaction
function getDaysSinceFirstTransaction(transactions) {
    if (transactions.length === 0) return 1;

    const dates = transactions.map((tx) => new Date(tx.transaction_date || tx.created_at));
    const earliest = new Date(Math.min(...dates));
    const now = new Date();
    const diff = now - earliest;
    return Math.max(1, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

// Update category pie chart
function updateCategoryChart(transactions) {
    const categoryTotals = {};

    transactions.forEach((tx) => {
        const cat = tx.category || "Other";
        categoryTotals[cat] = (categoryTotals[cat] || 0) + parseFloat(tx.amount || 0);
    });

    const labels = Object.keys(categoryTotals);
    const data = Object.values(categoryTotals);
    const colors = ["#FF6384", "#36A2EB", "#FFCE56", "#4BC0C0", "#9966FF", "#FF9F40", "#FF6384", "#C9CBCF"];

    const ctx = document.getElementById("categoryChart").getContext("2d");

    if (categoryChart) {
        categoryChart.destroy();
    }

    if (labels.length === 0) {
        categoryChart = new Chart(ctx, {
            type: "pie",
            data: {
                labels: ["No Data"],
                datasets: [
                    {
                        data: [1],
                        backgroundColor: ["#E0E0E0"],
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
            },
        });
        return;
    }

    categoryChart = new Chart(ctx, {
        type: "pie",
        data: {
            labels: labels,
            datasets: [
                {
                    data: data,
                    backgroundColor: colors,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "bottom",
                },
            },
        },
    });
}

// Update trend line chart
function updateTrendChart(transactions, period) {
    const dailyTotals = {};

    transactions.forEach((tx) => {
        const date = (tx.transaction_date || tx.created_at).split("T")[0];
        dailyTotals[date] = (dailyTotals[date] || 0) + parseFloat(tx.amount || 0);
    });

    const sortedDates = Object.keys(dailyTotals).sort();
    const labels = sortedDates.map((date) =>
        new Date(date).toLocaleDateString("en-IN", { month: "short", day: "numeric" }),
    );
    const data = sortedDates.map((date) => dailyTotals[date]);

    const ctx = document.getElementById("trendChart").getContext("2d");

    if (trendChart) {
        trendChart.destroy();
    }

    if (labels.length === 0) {
        trendChart = new Chart(ctx, {
            type: "line",
            data: {
                labels: ["No Data"],
                datasets: [
                    {
                        label: "Spending",
                        data: [0],
                        borderColor: "#E0E0E0",
                        backgroundColor: "rgba(224, 224, 224, 0.1)",
                        tension: 0.4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                },
            },
        });
        return;
    }

    trendChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Daily Spending",
                    data: data,
                    borderColor: "#4A90E2",
                    backgroundColor: "rgba(74, 144, 226, 0.1)",
                    tension: 0.4,
                    fill: true,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: "top",
                },
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function (value) {
                            return "₹" + value.toFixed(0);
                        },
                    },
                },
            },
        },
    });
}

// Display transactions in table
function displayTransactions(transactions) {
    const listElement = document.getElementById("transactionsList");
    const filter = document.getElementById("categoryFilter").value;
    const searchTerm = document.getElementById("searchInput").value.toLowerCase();

    let filtered = transactions;
    if (filter !== "all") {
        filtered = transactions.filter((tx) => tx.category === filter);
    }

    if (searchTerm) {
        filtered = filtered.filter((tx) => {
            const description = (tx.description || "").toLowerCase();
            const date = formatDate(tx.transaction_date || tx.created_at).toLowerCase();
            return description.includes(searchTerm) || date.includes(searchTerm);
        });
    }

    if (!filtered || filtered.length === 0) {
        listElement.innerHTML = '<tr><td colspan="4" class="loading">No transactions found</td></tr>';
        return;
    }

    filtered.sort((a, b) => {
        let valA, valB;

        if (sortColumn === "date") {
            valA = new Date(a.transaction_date || a.created_at);
            valB = new Date(b.transaction_date || b.created_at);
        } else if (sortColumn === "amount") {
            valA = parseFloat(a.amount);
            valB = parseFloat(b.amount);
        } else if (sortColumn === "description") {
            valA = (a.description || "").toLowerCase();
            valB = (b.description || "").toLowerCase();
        } else if (sortColumn === "category") {
            valA = (a.category || "").toLowerCase();
            valB = (b.category || "").toLowerCase();
        }

        if (sortDirection === "asc") {
            return valA > valB ? 1 : valA < valB ? -1 : 0;
        } else {
            return valA < valB ? 1 : valA > valB ? -1 : 0;
        }
    });

    let html = "";
    filtered.forEach((tx) => {
        const date = formatDate(tx.transaction_date || tx.created_at);
        const amount = formatCurrency(tx.amount);
        const category = tx.category || "Other";
        const description = tx.description || "-";
        const transactionId = tx.transaction_id;

        html += `
            <tr>
                <td>${date}</td>
                <td>${description}</td>
                <td><span class="category-tag">${category}</span></td>
                <td class="amount-cell">${amount}</td>
                <td class="actions-cell">
                    <button class="btn-icon btn-edit" onclick="openEditModal('${transactionId}')" title="Edit">✏️</button>
                    <button class="btn-icon btn-delete" onclick="deleteTransaction('${transactionId}')" title="Delete">🗑️</button>
                </td>
            </tr>
        `;
    });

    listElement.innerHTML = html;
}

// Load spending predictions
async function loadPredictions() {
    try {
        const result = await apiCall("/predictions", {
            method: "GET",
        });

        displayPredictions(result);
    } catch (error) {
        const content = document.getElementById("predictionsContent");
        content.innerHTML = `
            <div class="predictions-error">
                <p>⚠️ ${error.message}</p>
                <p class="predictions-hint">Add more transactions to enable predictions (minimum 3 required).</p>
            </div>
        `;
    }
}

// Display predictions in UI
function displayPredictions(data) {
    const content = document.getElementById("predictionsContent");

    if (!data.next_7_days || data.next_7_days.length === 0) {
        content.innerHTML = `
            <div class="predictions-error">
                <p>⚠️ Not enough data for predictions</p>
                <p class="predictions-hint">Add more transactions to enable predictions.</p>
            </div>
        `;
        return;
    }

    const accuracy = (data.model_accuracy * 100).toFixed(1);
    const accuracyClass = data.model_accuracy > 0.7 ? "good" : data.model_accuracy > 0.4 ? "medium" : "low";

    content.innerHTML = `
        <div class="predictions-summary">
            <div class="prediction-card">
                <p class="prediction-label">Next 7 Days</p>
                <p class="prediction-value">₹${data.next_7_days_total.toFixed(2)}</p>
            </div>
            <div class="prediction-card">
                <p class="prediction-label">Next 30 Days</p>
                <p class="prediction-value">₹${data.next_30_days_total.toFixed(2)}</p>
            </div>
            <div class="prediction-card">
                <p class="prediction-label">Daily Average (Est.)</p>
                <p class="prediction-value">₹${data.daily_average_predicted.toFixed(2)}</p>
            </div>
            <div class="prediction-card model-accuracy-card" style="display: none;">
                <p class="prediction-label">Model Accuracy</p>
                <p class="prediction-value accuracy-${accuracyClass}">${accuracy}%</p>
            </div>
        </div>
        <div class="predictions-details">
            <h3>Next 7 Days Breakdown</h3>
            <div class="predictions-table">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Predicted Amount</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.next_7_days
                            .map(
                                (day) => `
                            <tr>
                                <td>${formatDate(day.date)}</td>
                                <td class="amount-cell">₹${day.predicted_amount.toFixed(2)}</td>
                            </tr>
                        `,
                            )
                            .join("")}
                    </tbody>
                </table>
            </div>
        </div>
        <p class="predictions-note">
            💡 Predictions are based on your historical spending patterns using Linear Regression.
            Accuracy improves with more transaction data.
        </p>
    `;
}

// Logout
async function logout() {
    try {
        await apiCall("/logout", {
            method: "POST",
        });

        clearSession();
        showAlert("Logged out successfully", "success");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1000);
    } catch (error) {
        clearSession();
        window.location.href = "login.html";
    }
}

// Load user info for welcome message
async function loadUserInfo() {
    try {
        const result = await apiCall("/test-session-check", {
            method: "GET",
        });

        const firstName = result.first_name || result.username || "User";
        const welcomeMsg = document.getElementById("welcomeMessage");
        if (welcomeMsg) {
            welcomeMsg.textContent = `Welcome, ${firstName}!`;
        }
    } catch (error) {
        console.error("Error loading user info:", error);
    }
}

// Load streak data
async function loadStreak() {
    try {
        const result = await apiCall("/streaks", {
            method: "GET",
        });

        const streakCount = document.getElementById("streakCount");
        if (streakCount && result.streak) {
            streakCount.textContent = result.streak.current_streak || 0;
        }
    } catch (error) {
        console.error("Error loading streak:", error);
    }
}

// Load badges data
async function loadBadges() {
    try {
        const result = await apiCall("/badges", {
            method: "GET",
        });

        userBadges = result.badges || [];

        const badgesCount = document.getElementById("badgesCount");
        if (badgesCount) {
            badgesCount.textContent = userBadges.length;
        }

        if (result.new_badges && result.new_badges.length > 0) {
            showAlert(
                `🎉 New badge${result.new_badges.length > 1 ? "s" : ""} earned: ${result.new_badges.join(", ")}!`,
                "success",
            );
        }

        if (userBadges.length > 0) {
            displayBadges();
        }
    } catch (error) {
        console.error("Error loading badges:", error);
    }
}

// Display badges
function displayBadges() {
    const badgesGrid = document.getElementById("badgesGrid");
    const badgesSection = document.getElementById("badgesSection");

    if (!badgesGrid || !badgesSection) {
        console.error("Badges elements not found in DOM");
        return;
    }

    if (userBadges.length === 0) {
        badgesGrid.innerHTML = '<p class="no-badges">No badges earned yet. Keep tracking your expenses!</p>';
        badgesSection.style.display = "none";
        return;
    }

    badgesSection.style.display = "block";

    badgesGrid.innerHTML = userBadges
        .map(
            (badge) => `
        <div class="badge-card">
            <div class="badge-emoji">${badge.emoji || "🏆"}</div>
            <div class="badge-name">${badge.badge_name}</div>
            <div class="badge-description">${badge.description}</div>
            <div class="badge-date">Earned: ${formatDate(badge.earned_at)}</div>
        </div>
    `,
        )
        .join("");
}

// Setup badges toggle
function setupBadgesToggle() {
    const badgesPreview = document.getElementById("badgesPreview");
    if (badgesPreview) {
        badgesPreview.addEventListener("click", () => {
            const badgesSection = document.getElementById("badgesSection");
            if (badgesSection) {
                const isVisible = badgesSection.style.display !== "none" && badgesSection.style.display !== "";
                badgesSection.style.display = isVisible ? "none" : "block";

                if (!isVisible && userBadges.length > 0) {
                    setTimeout(() => {
                        badgesSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
                    }, 100);
                }
            }
        });
    }
}

// Modal functionality
const modal = document.getElementById("editModal");
const closeModal = document.getElementById("closeModal");
const cancelEdit = document.getElementById("cancelEdit");

if (closeModal) {
    closeModal.onclick = () => {
        modal.style.display = "none";
    };
}

if (cancelEdit) {
    cancelEdit.onclick = () => {
        modal.style.display = "none";
    };
}

window.onclick = (event) => {
    if (event.target == modal) {
        modal.style.display = "none";
    }
};

// Open edit modal
function openEditModal(transactionId) {
    const transaction = allTransactions.find((tx) => tx.transaction_id === transactionId);
    if (!transaction) {
        showAlert("Transaction not found", "error");
        return;
    }

    document.getElementById("editTransactionId").value = transactionId;
    document.getElementById("editAmount").value = transaction.amount;
    document.getElementById("editDescription").value = transaction.description;
    document.getElementById("editCategory").value = transaction.category || "Other";
    document.getElementById("editDate").value = transaction.transaction_date;

    modal.style.display = "block";
}

// Handle edit form submission
document.getElementById("editTransactionForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const transactionId = document.getElementById("editTransactionId").value;
    const amount = document.getElementById("editAmount").value;
    const description = document.getElementById("editDescription").value;
    const category = document.getElementById("editCategory").value;
    const date = document.getElementById("editDate").value;

    try {
        await apiCall(`/transactions/${transactionId}`, {
            method: "PUT",
            body: JSON.stringify({
                amount: parseFloat(amount),
                description: description,
                category: category,
                currency: "INR",
                transaction_date: date,
            }),
        });

        showAlert("Transaction updated successfully!", "success");
        modal.style.display = "none";
        loadDashboard();
        loadBadges();
    } catch (error) {
        const errorMsg = error.message || error.detail || "Error updating transaction";
        showAlert(errorMsg, "error");
    }
});

// Delete transaction
async function deleteTransaction(transactionId) {
    if (!confirm("Are you sure you want to delete this transaction?")) {
        return;
    }

    try {
        await apiCall(`/transactions/${transactionId}`, {
            method: "DELETE",
        });

        showAlert("Transaction deleted successfully!", "success");
        loadDashboard();
        loadBadges();
    } catch (error) {
        const errorMsg = error.message || error.detail || "Error deleting transaction";
        showAlert(errorMsg, "error");
    }
}
