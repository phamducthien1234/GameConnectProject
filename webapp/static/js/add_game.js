const API_BASE = window.GAMECONNECT_API_BASE;

const gameSelect = document.getElementById("gameSelect");
const riotSection = document.getElementById("riotSection");
const rankInput = document.getElementById("rank");
const rankHelp = document.getElementById("rankHelp");
const fetchRiotButton = document.getElementById("fetchRiotButton");

gameSelect.addEventListener("change", function () {
    const selectedOption = gameSelect.options[gameSelect.selectedIndex];
    const gameName = selectedOption.dataset.name || "";

    if (gameName.toLowerCase() === "league of legends") {
        riotSection.style.display = "block";
        rankHelp.textContent =
            "You can fetch your rank automatically using your Riot ID.";
    } else {
        riotSection.style.display = "none";
        rankHelp.textContent = "Enter your current rank.";
        clearRiotData();
    }
});

fetchRiotButton.addEventListener("click", fetchRiotProfile);

async function fetchRiotProfile() {
    const riotGameName = document
        .getElementById("riotGameName")
        .value
        .trim();

    const riotTagLine = document
        .getElementById("riotTagLine")
        .value
        .trim();

    const riotResult = document.getElementById("riotResult");

    if (!riotGameName || !riotTagLine) {
        riotResult.innerHTML = `
            <div class="alert alert-warning">
                Please enter both your Riot
                game name and Riot tag.
            </div>
        `;

        return;
    }

    fetchRiotButton.disabled = true;

    fetchRiotButton.innerHTML = `
        <span class="spinner-border spinner-border-sm"></span>
        Loading...
    `;

    riotResult.innerHTML = `
        <div class="alert alert-info">
            Retrieving Riot profile...
        </div>
    `;

    try {
        const url =
            `${API_BASE}/riot/account/` +
            encodeURIComponent(riotGameName) +
            "/" +
            encodeURIComponent(riotTagLine);

        console.log("Calling Riot API:", url);

        const apiResponse = await fetch(url);
        const responseText = await apiResponse.text();

        let data;

        try {
            data = JSON.parse(responseText);
        } catch {
            throw new Error("API returned an invalid response.");
        }

        console.log("Riot response:", data);

        if (!apiResponse.ok) {
            throw new Error(
                data.message ||
                data.error ||
                "Unable to retrieve Riot profile."
            );
        }

        const rankedEntries =
            data.ranked_entries ||
            data.rankedEntries ||
            data.league_entries ||
            [];

        let selectedRank = null;

        if (Array.isArray(rankedEntries)) {
            selectedRank = rankedEntries.find(
                entry => entry.queueType === "RANKED_SOLO_5x5"
            );

            if (!selectedRank && rankedEntries.length > 0) {
                selectedRank = rankedEntries[0];
            }
        }

        let rank = "Unranked";
        let leaguePoints = null;

        if (selectedRank) {
            const tier = selectedRank.tier || "";
            const division = selectedRank.rank || "";

            if (tier && division) {
                rank = `${tier} ${division}`;
            } else if (tier) {
                rank = tier;
            }

            leaguePoints = selectedRank.leaguePoints;
        }

        const puuid =
            data.puuid ||
            (data.account ? data.account.puuid : "") ||
            "";

        rankInput.value = rank;

        document.getElementById("riotGameNameHidden").value =
            riotGameName;

        document.getElementById("riotTagLineHidden").value =
            riotTagLine;

        document.getElementById("riotPuuid").value =
            puuid;

        document.getElementById("riotRank").value =
            rank;

        let rankDisplay = rank;

        if (
            leaguePoints !== null &&
            leaguePoints !== undefined
        ) {
            rankDisplay += ` (${leaguePoints} LP)`;
        }

        riotResult.innerHTML = `
            <div class="alert alert-success">
                <strong>
                    ✓ Riot profile found
                </strong>

                <hr>

                <div>
                    <strong>
                        Riot ID:
                    </strong>

                    ${escapeHtml(riotGameName)}
                    #
                    ${escapeHtml(riotTagLine)}
                </div>

                <div>
                    <strong>
                        Rank:
                    </strong>

                    ${escapeHtml(rankDisplay)}
                </div>

                ${
                    puuid
                        ? `
                            <div class="mt-2">
                                <small class="text-muted">
                                    Riot account verified
                                </small>
                            </div>
                        `
                        : ""
                }
            </div>
        `;
    } catch (error) {
        console.error("Riot API error:", error);

        riotResult.innerHTML = `
            <div class="alert alert-danger">
                <strong>
                    Unable to retrieve Riot profile.
                </strong>

                <br>

                ${escapeHtml(error.message)}
            </div>
        `;
    } finally {
        fetchRiotButton.disabled = false;
        fetchRiotButton.textContent = "Fetch Riot Profile";
    }
}

function clearRiotData() {
    document.getElementById("riotGameName").value = "";
    document.getElementById("riotTagLine").value = "";
    document.getElementById("riotGameNameHidden").value = "";
    document.getElementById("riotTagLineHidden").value = "";
    document.getElementById("riotPuuid").value = "";
    document.getElementById("riotRank").value = "";
    document.getElementById("riotResult").innerHTML = "";
}

function escapeHtml(text) {
    if (text === null || text === undefined) {
        return "";
    }

    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}