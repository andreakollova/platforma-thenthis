// Auto-hide toast (only if it exists)
setTimeout(() => {
  const toast = document.getElementById('toast-container');
  if (toast) {
    toast.style.transition = 'opacity 0.5s';
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 500);
  }
}, 4000);

// Toggle password visibility
function togglePasswordVisibility() {
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