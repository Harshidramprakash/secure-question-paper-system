/* ============================================================
   Secure Question Paper Assembly System — Client-side JS
   ============================================================ */

document.addEventListener('DOMContentLoaded', function () {
    // --- Mobile sidebar toggle ---
    const toggle = document.querySelector('.mobile-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });
    }

    // --- Auto-dismiss flash messages ---
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(function () { alert.remove(); }, 400);
        }, 5000);
    });

    // --- Confirm destructive actions ---
    document.querySelectorAll('[data-confirm]').forEach(function (el) {
        el.addEventListener('click', function (e) {
            var msg = el.getAttribute('data-confirm') || 'Are you sure?';
            if (!confirm(msg)) {
                e.preventDefault();
            }
        });
    });

    // --- Active nav highlighting ---
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(function (item) {
        if (item.getAttribute('href') === currentPath) {
            item.classList.add('active');
        }
    });
});
