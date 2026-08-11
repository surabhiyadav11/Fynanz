// Require login to view profile
requireLogin();

// Load profile data when page loads
document.addEventListener("DOMContentLoaded", () => {
    loadProfile();
});

// Handle logout
document.getElementById("logoutBtn").addEventListener("click", (e) => {
    e.preventDefault();
    logout();
});

// Load profile information
async function loadProfile() {
    try {
        const result = await apiCall("/test-session-check", {
            method: "GET",
        });

        document.getElementById("profileUsername").textContent = result.username || "-";
        document.getElementById("profileFirstName").textContent = result.first_name || "-";
        document.getElementById("profileLastName").textContent = result.last_name || "-";
        document.getElementById("profileEmail").textContent = result.email || "-";
    } catch (error) {
        showAlert(error.message, "error");
    }
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
