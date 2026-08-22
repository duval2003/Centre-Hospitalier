// Affiche ou masque un champ de mot de passe sans modifier sa valeur.
function togglePassword(inputId, button) {
    const input = document.getElementById(inputId);
    if (input.type === "password") {
        input.type = "text";
        button.textContent = "🙈";
    } else {
        input.type = "password";
        button.textContent = "👁";
    }
}

// Persistance du thème choisi entre les pages de l’application.
(function () {
    const storageKey = "hospital-theme";
    const savedTheme = localStorage.getItem(storageKey) || "light";

    document.documentElement.dataset.theme = savedTheme;

    function setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem(storageKey, theme);
        document.querySelectorAll("[data-theme-choice]").forEach((button) => {
            const selected = button.dataset.themeChoice === theme;
            button.classList.toggle("is-selected", selected);
            button.setAttribute("aria-pressed", selected ? "true" : "false");
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        setTheme(document.documentElement.dataset.theme);
        document.querySelectorAll("[data-theme-choice]").forEach((button) => {
            button.addEventListener("click", () => setTheme(button.dataset.themeChoice));
        });
    });
})();

// Gestion du menu latéral sur les écrans étroits.
document.addEventListener("DOMContentLoaded", () => {
    const toggle = document.querySelector("[data-app-sidebar-toggle]");
    const sidebar = document.querySelector("[data-app-sidebar]");

    if (!toggle || !sidebar) {
        return;
    }

    toggle.addEventListener("click", () => {
        const isOpen = sidebar.classList.toggle("is-open");
        toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    });

    sidebar.querySelectorAll("a").forEach((link) => {
        link.addEventListener("click", () => {
            sidebar.classList.remove("is-open");
            toggle.setAttribute("aria-expanded", "false");
        });
    });
});