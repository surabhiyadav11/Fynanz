// Common utilities and configuration

const API_BASE_URL = "http://localhost:8000";
// const API_BASE_URL = "https://540732.site.bot-hosting.cloud";

// Helper function to show alerts
function showAlert(message, type = "info") {
    const alertBox = document.getElementById("alertBox");
    const alert = document.createElement("div");
    alert.className = `alert alert-${type}`;
    alert.textContent = message;

    alertBox.appendChild(alert);

    setTimeout(() => {
        alert.remove();
    }, 3000);
}

// Helper to get session from localStorage
function getSession() {
    const sessionStr = localStorage.getItem("fynanz_session");
    if (sessionStr) {
        try {
            return JSON.parse(sessionStr);
        } catch {
            return null;
        }
    }
    return null;
}

// Helper to save session to localStorage
function saveSession(sessionData) {
    localStorage.setItem("fynanz_session", JSON.stringify(sessionData));
}

// Helper to clear session
function clearSession() {
    localStorage.removeItem("fynanz_session");
}

// Check if user is logged in
function isUserLoggedIn() {
    const session = getSession();
    return session && session.user_id && session.session_id;
}

// Redirect to login if not logged in
function requireLogin() {
    if (!isUserLoggedIn()) {
        window.location.href = "login.html";
    }
}

// Redirect to dashboard if already logged in
function redirectIfLoggedIn() {
    if (isUserLoggedIn()) {
        window.location.href = "dashboard.html";
    }
}

// Make API call with session
async function apiCall(endpoint, options = {}) {
    const session = getSession();
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };

    if (session) {
        const sessionJson = JSON.stringify(session);
        const encoded = btoa(sessionJson);
        headers["Authorization"] = `Bearer ${encoded}`;
    }

    const finalOptions = {
        ...options,
        headers: headers,
    };

    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, finalOptions);

        let data;
        try {
            data = await response.json();
        } catch {
            data = { detail: "Server error" };
        }

        if (!response.ok) {
            const errorMessage = data.detail || data.message || `Error: ${response.status}`;
            throw new Error(errorMessage);
        }

        return data;
    } catch (error) {
        if (error instanceof Error) {
            throw error;
        }
        throw new Error("Network error");
    }
}

// Format currency
function formatCurrency(amount, currency = "INR") {
    const symbols = {
        INR: "₹",
        USD: "$",
        EUR: "€",
    };

    const symbol = symbols[currency] || currency;
    return `${symbol}${amount.toFixed(2)}`;
}

// Format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-IN");
}
