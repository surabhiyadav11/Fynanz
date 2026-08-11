// Check if already logged in
redirectIfLoggedIn();

// Handle register form submission
document.getElementById("registerForm").addEventListener("submit", async (e) => {
    e.preventDefault();

    const username = document.getElementById("username").value;
    const firstName = document.getElementById("firstName").value;
    const lastName = document.getElementById("lastName").value;
    const email = document.getElementById("email").value;
    const password = document.getElementById("registerPassword").value;

    try {
        const result = await apiCall("/register", {
            method: "POST",
            body: JSON.stringify({
                username: username,
                first_name: firstName,
                last_name: lastName,
                email: email,
                password: password,
            }),
        });

        showAlert("Registration successful! Redirecting to login...", "success");

        setTimeout(() => {
            window.location.href = "login.html";
        }, 1500);
    } catch (error) {
        showAlert(error.message, "error");
    }
});
