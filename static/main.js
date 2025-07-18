document.addEventListener('DOMContentLoaded', () => {

  // --- Toast zmizne ---
  setTimeout(() => {
    const toast = document.getElementById('toast-container');
    if (toast) {
      toast.style.transition = 'opacity 0.5s';
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 500);
    }
  }, 4000);

  // --- Toggle hesla ---
  window.togglePasswordVisibility = function () {
    const input = document.getElementById("floatingPassword");
    const icon = document.getElementById("toggle-icon");

    if (input.type === "password") {
      input.type = "text";
    } else {
      input.type = "password";
    }

    icon.classList.toggle("fa-eye");
    icon.classList.toggle("fa-eye-slash");
  }

  // --- Prehľad preview ---
  document.querySelectorAll('.open-preview').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('modal-title').textContent = btn.dataset.title;
      document.getElementById('modal-description').textContent = btn.dataset.description;

      const category = btn.dataset.category;
      const subcategory = btn.dataset.subcategory;
      const icons = {
        "Python": "fab fa-python",
        "JavaScript": "fab fa-js",
        "HTML": "fab fa-html5",
        "CSS": "fab fa-css3-alt",
        "SQL": "fas fa-database"
      };
      const iconClass = icons[category] || "fas fa-code";
      document.getElementById('modal-category').innerHTML = `<i class="${iconClass} me-1"></i> ${category} / ${subcategory}`;

      document.getElementById('modal-author-name').textContent = btn.dataset.authorName;
      document.getElementById('modal-author-photo').src = btn.dataset.authorPhoto;
      document.getElementById('modal-author').style.display = 'flex';

      const answers = btn.dataset.answers;
      const modalCode = document.getElementById('modal-code');
      if (answers && answers.trim()) {
        const highlight = ["class", "def", "self", "print", "Zviera", "zvuk"];
        const unique = answers.split(', ').filter((v, i, a) => a.indexOf(v) === i);
        const formatted = unique.map(word =>
          highlight.includes(word) ? `<span class="text-primary">${word}</span>` : word
        ).join(', ');
        modalCode.innerHTML = `Kód na precvičenie: ${formatted}`;
        modalCode.classList.remove('d-none');
      } else {
        modalCode.classList.add('d-none');
      }
    });
  });

});
