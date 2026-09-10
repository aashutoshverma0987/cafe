document.addEventListener("DOMContentLoaded", function () {

    const passwordInput = document.getElementById("password");
    const passwordToggle = document.getElementById("passwordToggle");

    const loginForm = document.getElementById("loginForm");
    const loginButton = document.getElementById("loginButton");


    // =====================================================
    // SHOW / HIDE PASSWORD
    // =====================================================

    if (passwordToggle && passwordInput) {

        passwordToggle.addEventListener("click", function () {

            if (passwordInput.type === "password") {

                passwordInput.type = "text";

                passwordToggle.textContent = "🙈";

                passwordToggle.setAttribute(
                    "aria-label",
                    "Hide password"
                );

            } else {

                passwordInput.type = "password";

                passwordToggle.textContent = "👁";

                passwordToggle.setAttribute(
                    "aria-label",
                    "Show password"
                );

            }

        });

    }


    // =====================================================
    // LOGIN BUTTON LOADING
    // =====================================================

    if (loginForm && loginButton) {

        loginForm.addEventListener("submit", function () {

            loginButton.classList.add("loading");

            loginButton.disabled = true;

        });

    }


    // =====================================================
    // AUTO FOCUS EMAIL
    // =====================================================

    const emailInput = document.getElementById("email");

    if (emailInput) {

        emailInput.focus();

    }


    // =====================================================
    // REMOVE ERROR WHEN USER STARTS TYPING
    // =====================================================

    if (emailInput) {

        emailInput.addEventListener("input", function () {

            const error =
                document.getElementById("emailError");

            if (error) {

                error.textContent = "";

            }

        });

    }


    if (passwordInput) {

        passwordInput.addEventListener("input", function () {

            const error =
                document.getElementById("passwordError");

            if (error) {

                error.textContent = "";

            }

        });

    }

});