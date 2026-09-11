document.addEventListener("DOMContentLoaded", function () {
    const statusBox = document.getElementById("analyticsJobStatus");

    if (!statusBox) {
        return;
    }

    const statusUrl = statusBox.dataset.statusUrl;

    if (!statusUrl) {
        return;
    }

    const title = document.getElementById("analyticsStatusTitle");
    const text = document.getElementById("analyticsStatusText");
    const badge = document.getElementById("analyticsStatusBadge");
    const spinner = document.getElementById("analyticsStatusSpinner");

    const terminalStates = new Set([
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "INTERRUPTED"
    ]);

    function setBadge(state) {
        badge.textContent = state;
        badge.className = "badge";

        if (state === "COMPLETED") {
            badge.classList.add("bg-success");
        } else if (
            ["FAILED", "CANCELLED", "INTERRUPTED"].includes(state)
        ) {
            badge.classList.add("bg-danger");
        } else if (state === "RUNNING") {
            badge.classList.add("bg-primary");
        } else {
            badge.classList.add(
                "bg-warning",
                "text-dark"
            );
        }
    }

    async function checkStatus() {
        try {
            const response = await fetch(
                statusUrl,
                {
                    method: "GET",
                    headers: {
                        "Accept": "application/json"
                    }
                }
            );

            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.message ||
                    "Unable to check analytics status."
                );
            }

            const state = data.state || "UNKNOWN";

            setBadge(state);

            if (state === "PENDING") {

                title.textContent =
                    "Analytics job is waiting";

                text.textContent =
                    "Amazon EMR is preparing the Spark analytics job.";

            } else if (state === "RUNNING") {

                title.textContent =
                    "Analytics job is running";

                text.textContent =
                    "Amazon EMR is processing the latest GameConnect events.";

            } else if (state === "COMPLETED") {

                title.textContent =
                    "Analytics update completed";

                text.textContent =
                    "Loading the latest analytics results...";

                spinner.classList.add(
                    "d-none"
                );

                setTimeout(function () {
                    window.location.reload();
                }, 1500);

                return;

            } else if (terminalStates.has(state)) {

                title.textContent =
                    "Analytics update did not complete";

                text.textContent =
                    data.message ||
                    `EMR job ended with status ${state}.`;

                spinner.classList.add(
                    "d-none"
                );

                return;

            } else {

                title.textContent =
                    "Checking analytics job";

                text.textContent =
                    `Current EMR status: ${state}`;
            }

            setTimeout(
                checkStatus,
                5000
            );

        } catch (error) {

            console.error(
                "Analytics status error:",
                error
            );

            title.textContent =
                "Unable to check analytics status";

            text.textContent =
                "GameConnect will try again automatically.";

            badge.textContent =
                "RETRYING";

            badge.className =
                "badge bg-secondary";

            setTimeout(
                checkStatus,
                8000
            );
        }
    }

    checkStatus();
});