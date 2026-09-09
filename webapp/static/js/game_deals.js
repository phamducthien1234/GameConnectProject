const API_BASE =
    "https://q4bibcud7b.execute-api.us-east-1.amazonaws.com/";


document.addEventListener("DOMContentLoaded", function () {

    const searchButton =
        document.getElementById("searchButton");

    const gameSearch =
        document.getElementById("gameSearch");


    searchButton.addEventListener(
        "click",
        searchDeals
    );


    gameSearch.addEventListener(
        "keydown",
        function (event) {

            if (event.key === "Enter") {
                searchDeals();
            }

        }
    );

});


async function searchDeals() {

    const query =
        document
            .getElementById("gameSearch")
            .value
            .trim();


    if (!query) {

        showNotification(
            "Please enter a game name."
        );

        return;
    }


    const results =
        document.getElementById("results");

    const loading =
        document.getElementById("loading");


    results.innerHTML = "";

    loading.classList.remove("d-none");


    try {

        const url =
            `${API_BASE}/cheapshark/games/`
            + encodeURIComponent(query);


        const response =
            await fetch(url);


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data.message ||
                "Unable to search games"
            );

        }


        if (
            !data.games ||
            data.games.length === 0
        ) {

            results.innerHTML = `

                <div class="col-12">

                    <div class="alert alert-warning">
                        No games found.
                    </div>

                </div>

            `;

            return;
        }


        data.games.forEach(function (game) {

            results.innerHTML += `

                <div class="col-md-6 col-lg-4 mb-4">

                    <div class="card h-100 shadow-sm">


                        ${
                            game.thumb
                            ? `
                                <img
                                    src="${game.thumb}"
                                    class="card-img-top"
                                    alt="${escapeHtml(game.external)}"
                                    style="
                                        height: 180px;
                                        object-fit: cover;
                                    "
                                >
                            `
                            : ""
                        }


                        <div class="card-body">


                            <h5 class="card-title">

                                ${escapeHtml(game.external)}

                            </h5>


                            <p class="card-text">

                                Cheapest price:

                                <strong>

                                    ${
                                        game.cheapest
                                        ? "$" + game.cheapest
                                        : "N/A"
                                    }

                                </strong>

                            </p>


                            ${
                                game.steamAppID
                                ? `
                                    <span class="badge bg-secondary">
                                        Steam
                                    </span>
                                `
                                : ""
                            }


                            <div class="mt-3">


                                ${
                                    game.cheapestDealID
                                    ? `
                                        <a
                                            href="https://www.cheapshark.com/redirect?dealID=${encodeURIComponent(game.cheapestDealID)}"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            class="btn btn-success"
                                        >
                                            View Deal
                                        </a>
                                    `
                                    : ""
                                }


                            </div>


                        </div>

                    </div>

                </div>

            `;

        });


    } catch (error) {

        console.error(error);


        results.innerHTML = `

            <div class="col-12">

                <div class="alert alert-danger">

                    ${escapeHtml(error.message)}

                </div>

            </div>

        `;

    } finally {

        loading.classList.add("d-none");

    }

}


function escapeHtml(value) {

    const div =
        document.createElement("div");

    div.textContent =
        value ?? "";

    return div.innerHTML;

}


function showNotification(message) {

    let container =
        document.querySelector(
            ".flash-container"
        );


    if (!container) {

        container =
            document.createElement("div");

        container.className =
            "flash-container";

        document.body.appendChild(
            container
        );

    }


    const notification =
        document.createElement("div");

    notification.className =
        "flash-message";

    notification.textContent =
        message;


    container.appendChild(
        notification
    );


    setTimeout(function () {

        notification.classList.add("show");

    }, 100);


    setTimeout(function () {

        notification.classList.remove("show");

        setTimeout(function () {

            notification.remove();

        }, 500);

    }, 3000);

}