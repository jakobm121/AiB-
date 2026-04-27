
document.addEventListener("DOMContentLoaded", () => {
  const bookmakerToggles = document.querySelectorAll(".bookmaker-toggle");

  bookmakerToggles.forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".bookmaker-card");
      const details = card ? card.querySelector(".bookmaker-card__details") : null;
      if (!details) return;

      const isOpen = btn.getAttribute("aria-expanded") === "true";
      btn.setAttribute("aria-expanded", String(!isOpen));

      if (isOpen) {
        details.style.maxHeight = null;
        details.classList.remove("is-open");
        btn.textContent = "Detailed Review";
      } else {
        details.style.maxHeight = details.scrollHeight + "px";
        details.classList.add("is-open");
        btn.textContent = "Hide Review";
      }
    });
  });
});
