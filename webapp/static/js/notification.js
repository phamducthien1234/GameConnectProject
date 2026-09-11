document.addEventListener("DOMContentLoaded", function () {
    const notifications = document.querySelectorAll(".flash-message");

    notifications.forEach(function (notification) {
        setTimeout(function () {
            notification.classList.add("show");
        }, 100);

        setTimeout(function () {
            notification.classList.remove("show");

            setTimeout(function () {
                notification.remove();
            }, 500);
        }, 3000);
    });
});