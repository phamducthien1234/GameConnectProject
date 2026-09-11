document.addEventListener("DOMContentLoaded", function () {

    const notifications = document.querySelectorAll(".flash-message");

    notifications.forEach(function (notification) {

        // Show notification
        setTimeout(function () {
            notification.classList.add("show");
        }, 100);

        // Automatically hide after 3 seconds
        setTimeout(function () {
            notification.classList.remove("show");

            // Remove from page after animation
            setTimeout(function () {
                notification.remove();
            }, 500);

        }, 3000);
    });

});