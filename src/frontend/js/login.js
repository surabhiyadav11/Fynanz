// Check if already logged in
redirectIfLoggedIn();

// Handle login form submission
document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const identity = document.getElementById("loginIdentity").value;
    const password = document.getElementById("loginPassword").value;

    try {
        const result = await apiCall("/login", {
            method: "POST",
            body: JSON.stringify({
                identity: identity,
                password: password,
            }),
        });

        if (result.session) {
            saveSession(result.session);
        }

        showAlert("Login successful! Redirecting...", "success");
        setTimeout(() => {
            window.location.href = "dashboard.html";
        }, 500);
    } catch (error) {
        showAlert(error.message, "error");
    }
});
