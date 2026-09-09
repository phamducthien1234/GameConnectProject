import re


RANK_SYSTEMS = {

    "Valorant": {
        "Iron": 1,
        "Bronze": 2,
        "Silver": 3,
        "Gold": 4,
        "Platinum": 5,
        "Diamond": 6,
        "Ascendant": 7,
        "Immortal": 8,
        "Radiant": 9,
    },

    "League of Legends": {
        "Iron": 1,
        "Bronze": 2,
        "Silver": 3,
        "Gold": 4,
        "Platinum": 5,
        "Emerald": 6,
        "Diamond": 7,
        "Master": 8,
        "Grandmaster": 9,
        "Challenger": 10,
    },

    "Counter-Strike 2": {
        "Silver": 1,
        "Gold Nova": 2,
        "Master Guardian": 3,
        "Distinguished Master Guardian": 4,
        "Legendary Eagle": 5,
        "Supreme": 6,
        "Global Elite": 7,
    },

    "Dota 2": {
        "Herald": 1,
        "Guardian": 2,
        "Crusader": 3,
        "Archon": 4,
        "Legend": 5,
        "Ancient": 6,
        "Divine": 7,
        "Immortal": 8,
    },

    "Apex Legends": {
        "Rookie": 1,
        "Bronze": 2,
        "Silver": 3,
        "Gold": 4,
        "Platinum": 5,
        "Diamond": 6,
        "Master": 7,
        "Apex Predator": 8,
    },

    "Fortnite": {
        "Bronze": 1,
        "Silver": 2,
        "Gold": 3,
        "Platinum": 4,
        "Diamond": 5,
        "Elite": 6,
        "Champion": 7,
        "Unreal": 8,
    },

    "Rocket League": {
        "Bronze": 1,
        "Silver": 2,
        "Gold": 3,
        "Platinum": 4,
        "Diamond": 5,
        "Champion": 6,
        "Grand Champion": 7,
        "Supersonic Legend": 8,
    },

    "Overwatch 2": {
        "Bronze": 1,
        "Silver": 2,
        "Gold": 3,
        "Platinum": 4,
        "Diamond": 5,
        "Master": 6,
        "Grandmaster": 7,
        "Champion": 8,
    },

    "Teamfight Tactics": {
        "Iron": 1,
        "Bronze": 2,
        "Silver": 3,
        "Gold": 4,
        "Platinum": 5,
        "Emerald": 6,
        "Diamond": 7,
        "Master": 8,
        "Grandmaster": 9,
        "Challenger": 10,
    },
    "Minecraft": {}
}


def get_rank_value(game_name, rank):
    """
    Convert a player's rank into a numeric value
    based on the game's ranking system.
    """

    if not game_name or not rank:
        return None

    rank = str(rank).strip()
    
    system = RANK_SYSTEMS.get(game_name)

    if not system:
        return None

    # Exact match first
    if rank in system:
        return float(system[rank])

    # Handle divisions such as:
    # Iron IV
    # Gold II
    # Diamond I

    rank_lower = rank.lower()

    divisions = {
        "iv": 0.0,
        "iii": 0.1,
        "ii": 0.2,
        "i": 0.3,
    }

    for tier, value in system.items():

        if rank_lower.startswith(tier.lower()):

            for division, division_value in divisions.items():

                if re.search(
                    rf"\b{division}\b",
                    rank_lower
                ):
                    return system[tier] + division_value

            return float(system[tier])

    return None


def calculate_match_score(current_player, candidate):

    # Base score
    score = 30

    # ========================================
    # GAME
    # ========================================

    current_game = current_player.get("game_name", "")
    candidate_game = candidate.get("game_name", "")

    # Different games should not normally
    # be matched together.
    if (
        current_game
        and candidate_game
        and current_game.lower() != candidate_game.lower()
    ):
        return 0

    # ========================================
    # RANK - 25 POINTS
    # ========================================

    current_rank = current_player.get("rank", "")
    candidate_rank = candidate.get("rank", "")

    current_rank_value = get_rank_value(
        current_game,
        current_rank
    )

    candidate_rank_value = get_rank_value(
        candidate_game,
        candidate_rank
    )

    if (
        current_rank_value is not None
        and candidate_rank_value is not None
    ):

        rank_difference = abs(
            current_rank_value
            - candidate_rank_value
        )

        if rank_difference == 0:
            score += 25

        elif rank_difference <= 1:
            score += 20

        elif rank_difference <= 2:
            score += 10

    elif (
        current_rank
        and candidate_rank
        and current_rank.lower()
        == candidate_rank.lower()
    ):
        # Unknown/special rank but exact same text
        score += 25

    # ========================================
    # ROLE - 20 POINTS
    # ========================================

    current_role = current_player.get(
        "role",
        ""
    )

    candidate_role = candidate.get(
        "role",
        ""
    )

    if (
        current_role
        and candidate_role
        and current_role.lower()
        == candidate_role.lower()
    ):
        score += 20

    # ========================================
    # REGION - 15 POINTS
    # ========================================

    current_region = current_player.get(
        "region",
        ""
    )

    candidate_region = candidate.get(
        "region",
        ""
    )

    if (
        current_region
        and candidate_region
        and current_region.lower()
        == candidate_region.lower()
    ):
        score += 15

    # ========================================
    # AVAILABILITY - 10 POINTS
    # ========================================

    current_availability = current_player.get(
        "availability",
        ""
    )

    candidate_availability = candidate.get(
        "availability",
        ""
    )

    if (
        current_availability
        and candidate_availability
        and current_availability.lower()
        == candidate_availability.lower()
    ):
        score += 10

    return score