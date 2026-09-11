const searchInput = document.getElementById("gameSearch");
const searchButton = document.getElementById("searchButton");
const resultsContainer = document.getElementById("results");
const loading = document.getElementById("loading");

const featuredGames = [
    {
        name: "Cyberpunk 2077",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/1091500/header.jpg"
    },
    {
        name: "Grand Theft Auto V",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/271590/header.jpg"
    },
    {
        name: "Red Dead Redemption 2",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/1174180/header.jpg"
    },
    {
        name: "Elden Ring",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/1245620/header.jpg"
    },
    {
        name: "The Witcher 3",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/292030/header.jpg"
    },
    {
        name: "Hogwarts Legacy",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/990080/header.jpg"
    },
    {
        name: "Baldur's Gate 3",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/1086940/header.jpg"
    },
    {
        name: "Resident Evil 4",
        image: "https://cdn.cloudflare.steamstatic.com/steam/apps/2050650/header.jpg"
    }
];

const refreshFeaturedButton = document.getElementById("refreshFeatured");

if (refreshFeaturedButton) {
    refreshFeaturedButton.addEventListener(
        "click",
        displayFeaturedGames
    );
}

function shuffleArray(array) {
    return [...array].sort(() => Math.random() - 0.5);
}

function displayFeaturedGames() {
    resultsContainer.innerHTML = "";

    const randomGames = shuffleArray(featuredGames).slice(0, 6);

    randomGames.forEach(game => {
        const card = document.createElement("div");

        card.className = "col-md-6 col-lg-4 mb-4";

        card.innerHTML = `
            <div class="card h-100 shadow-sm">
                <img
                    src="${game.image}"
                    class="card-img-top"
                    alt="${game.name}"
                    style="height: 180px; object-fit: cover;"
                >

                <div class="card-body d-flex flex-column">
                    <h5 class="card-title">
                        ${game.name}
                    </h5>

                    <p class="text-muted">
                        Search GameConnect to find current deals.
                    </p>

                    <button
                        class="btn btn-primary mt-auto featured-search"
                        data-game="${game.name}"
                    >
                        Find Deals
                    </button>
                </div>
            </div>
        `;

        resultsContainer.appendChild(card);
    });

    document.querySelectorAll(".featured-search").forEach(button => {
        button.addEventListener("click", function () {
            const gameName = this.dataset.game;

            searchInput.value = gameName;

            searchGames(gameName);
        });
    });
}

async function searchGames(gameName = null) {
    const searchValue = gameName || searchInput.value.trim();

    if (!searchValue) {
        return;
    }

    loading.classList.remove("d-none");
    resultsContainer.innerHTML = "";

    try {
        const response = await fetch(
            `https://q4bibcud7b.execute-api.us-east-1.amazonaws.com/cheapshark/games/${encodeURIComponent(searchValue)}`
        );

        const data = await response.json();

        loading.classList.add("d-none");

        if (!response.ok) {
            resultsContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-danger">
                        Unable to retrieve game deals.
                    </div>
                </div>
            `;

            return;
        }

        let games = data;

        if (data.games) {
            games = data.games;
        }

        if (!Array.isArray(games) || games.length === 0) {
            resultsContainer.innerHTML = `
                <div class="col-12">
                    <div class="alert alert-info">
                        No games were found.
                    </div>
                </div>
            `;

            return;
        }

        displaySearchResults(games);
    } catch (error) {
        console.error(error);

        loading.classList.add("d-none");

        resultsContainer.innerHTML = `
            <div class="col-12">
                <div class="alert alert-danger">
                    Unable to connect to the Game Deals service.
                </div>
            </div>
        `;
    }
}

function displaySearchResults(games) {
    resultsContainer.innerHTML = "";

    games.forEach(game => {
        const card = document.createElement("div");

        card.className = "col-md-6 col-lg-4 mb-4";

        const image = game.thumb || "";

        const price = game.cheapest_price
            ? `$${game.cheapest_price}`
            : "Price unavailable";

        card.innerHTML = `
            <div class="card h-100 shadow-sm">
                ${
                    image
                        ? `
                            <img
                                src="${image}"
                                class="card-img-top"
                                alt="${game.name}"
                                style="height: 180px; object-fit: cover;"
                            >
                        `
                        : ""
                }

                <div class="card-body">
                    <h5 class="card-title">
                        ${game.name || "Unknown Game"}
                    </h5>

                    <p>
                        <strong>Cheapest Price:</strong>
                        ${price}
                    </p>

                    ${
                        game.steam_app_id
                            ? `
                                <p class="text-muted">
                                    Steam App ID:
                                    ${game.steam_app_id}
                                </p>
                            `
                            : ""
                    }
                </div>
            </div>
        `;

        resultsContainer.appendChild(card);
    });
}

searchButton.addEventListener("click", function () {
    searchGames();
});

searchInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        searchGames();
    }
});

displayFeaturedGames();