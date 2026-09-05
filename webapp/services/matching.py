RANK_ORDER = {
    "Iron": 1,
    "Bronze": 2,
    "Silver": 3,
    "Gold": 4,
    "Platinum": 5,
    "Diamond": 6,
    "Ascendant": 7,
    "Immortal": 8,
    "Radiant": 9,

    # League of Legends
    "Iron IV": 1,
    "Iron III": 1,
    "Iron II": 1,
    "Iron I": 1,
    "Bronze IV": 2,
    "Bronze III": 2,
    "Bronze II": 2,
    "Bronze I": 2,
    "Silver IV": 3,
    "Silver III": 3,
    "Silver II": 3,
    "Silver I": 3,
    "Gold IV": 4,
    "Gold III": 4,
    "Gold II": 4,
    "Gold I": 4,
    "Platinum IV": 5,
    "Platinum III": 5,
    "Platinum II": 5,
    "Platinum I": 5,
    "Emerald IV": 6,
    "Emerald III": 6,
    "Emerald II": 6,
    "Emerald I": 6,
    "Diamond IV": 7,
    "Diamond III": 7,
    "Diamond II": 7,
    "Diamond I": 7,
}


def calculate_match_score(current_player, candidate):
    score = 30

    # --------------------------------
    # Rank: 25 points
    # --------------------------------
    current_rank = current_player.get("rank", "")
    candidate_rank = candidate.get("rank", "")

    current_rank_value = RANK_ORDER.get(current_rank)
    candidate_rank_value = RANK_ORDER.get(candidate_rank)

    if current_rank_value and candidate_rank_value:
        rank_difference = abs(
            current_rank_value - candidate_rank_value
        )

        if rank_difference == 0:
            score += 25
        elif rank_difference == 1:
            score += 20
        elif rank_difference == 2:
            score += 10

    elif current_rank == candidate_rank:
        score += 25

    # --------------------------------
    # Role: 20 points
    # --------------------------------
    current_role = current_player.get("role", "")
    candidate_role = candidate.get("role", "")

    if current_role and current_role == candidate_role:
        score += 20

    # --------------------------------
    # Region: 15 points
    # --------------------------------
    if (
        current_player.get("region")
        and current_player.get("region")
        == candidate.get("region")
    ):
        score += 15

    # --------------------------------
    # Availability: 10 points
    # --------------------------------
    if (
        current_player.get("availability")
        and current_player.get("availability")
        == candidate.get("availability")
    ):
        score += 10

    return score