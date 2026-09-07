from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify
)
from boto3.dynamodb.conditions import Key, Attr
from werkzeug.security import (generate_password_hash,check_password_hash)
from config import Config
from services.dynamodb import get_table
from services.matching import calculate_match_score
import uuid
from datetime import datetime, timezone


app = Flask(__name__)
app.config.from_object(Config)


# =========================
# HOME
# =========================

@app.route("/")
def index():
     return render_template("index.html")


# =========================
# DYNAMODB TEST
# =========================

@app.route("/test-dynamodb")
def test_dynamodb():

    try:

        table = get_table(
            app.config["USERS_TABLE"]
        )

        response = table.scan(
            Limit=1
        )

        return {
            "status": "success",
            "message": "Flask is connected to GameConnectUsers",
            "table": app.config["USERS_TABLE"],
            "region": app.config["AWS_REGION"],
            "items_found": response["Count"]
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }, 500


# =========================
# REGISTER
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get(
        "username",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    region = request.form.get(
        "region",
        ""
    ).strip()

    # Validate fields

    if not username or not email or not password or not region:

        flash("Please complete all fields.")

        return redirect(
            url_for("register")
        )

    # Validate password

    if len(password) < 8:

        flash(
            "Password must be at least 8 characters."
        )

        return redirect(
            url_for("register")
        )

    users_table = get_table(
        app.config["USERS_TABLE"]
    )

    # Check username

    username_response = users_table.query(
        IndexName="username-index",

        KeyConditionExpression="username = :username",

        ExpressionAttributeValues={
            ":username": username
        }
    )

    if username_response["Items"]:

        flash(
            "Username is already taken."
        )

        return redirect(
            url_for("register")
        )

    # Check email

    email_response = users_table.query(
        IndexName="email-index",

        KeyConditionExpression="email = :email",

        ExpressionAttributeValues={
            ":email": email
        }
    )

    if email_response["Items"]:

        flash(
            "Email is already registered."
        )

        return redirect(
            url_for("register")
        )

    # Create user ID

    user_id = str(
        uuid.uuid4()
    )

    # Hash password

    password_hash = generate_password_hash(
        password
    )

    # Create user

    user = {

        "user_id": user_id,

        "username": username,

        "email": email,

        "password_hash": password_hash,

        "role": "player",

        "region": region,

        "bio": "",

        "profile_image_url": "",

        "created_at":datetime.now(timezone.utc).isoformat()
    }

    # Save to DynamoDB

    users_table.put_item(
        Item=user,

        ConditionExpression=
            "attribute_not_exists(user_id)"
    )

    flash(
        "Registration successful. Please log in."
    )

    return redirect(
        url_for("login")
    )


# =========================
# LOGIN
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "GET":

        return render_template(
            "login.html"
        )

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not username or not password:

        flash(
            "Please enter username and password."
        )

        return redirect(
            url_for("login")
        )

    users_table = get_table(
        app.config["USERS_TABLE"]
    )

    # Find user using username GSI

    response = users_table.query(

        IndexName="username-index",

        KeyConditionExpression=
            "username = :username",

        ExpressionAttributeValues={
            ":username": username
        }
    )

    users = response.get(
        "Items",
        []
    )

    if not users:

        flash(
            "Invalid username or password."
        )

        return redirect(
            url_for("login")
        )

    user = users[0]

    # Check password

    if not check_password_hash(
        user["password_hash"],
        password
    ):

        flash(
            "Invalid username or password."
        )

        return redirect(
            url_for("login")
        )

    # Create Flask session

    session["user_id"] = user["user_id"]

    session["username"] = user["username"]

    return redirect(
        url_for("dashboard")
    )


# =========================
# DASHBOARD
# =========================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        flash(
            "Please log in first."
        )

        return redirect(
            url_for("login")
        )

    users_table = get_table(
        app.config["USERS_TABLE"]
    )

    response = users_table.get_item(

        Key={
            "user_id": session["user_id"]
        }
    )

    user = response.get(
        "Item"
    )

    if not user:

        session.clear()

        flash(
            "User account could not be found."
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "dashboard.html",
        user=user
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():

    if "user_id" not in session:

        flash("Please log in first.")

        return redirect(
            url_for("login")
        )

    users_table = get_table(
        app.config["USERS_TABLE"]
    )

    player_games_table = get_table(
        app.config["PLAYER_GAMES_TABLE"]
    )

    user_id = session["user_id"]


    # -------------------------
    # Update profile
    # -------------------------

    if request.method == "POST":

        region = request.form.get(
            "region",
            ""
        ).strip()

        bio = request.form.get(
            "bio",
            ""
        ).strip()

        users_table.update_item(

            Key={
                "user_id": user_id
            },

            UpdateExpression=
                "SET #region = :region, bio = :bio",

            ExpressionAttributeNames={
                "#region": "region"
            },

            ExpressionAttributeValues={
                ":region": region,
                ":bio": bio
            }
        )

        flash(
            "Profile updated successfully."
        )

        return redirect(
            url_for("profile")
        )


    # -------------------------
    # Get user
    # -------------------------

    response = users_table.get_item(

        Key={
            "user_id": user_id
        }
    )

    user = response.get("Item")


    if not user:

        session.clear()

        flash(
            "User account could not be found."
        )

        return redirect(
            url_for("login")
        )


    # -------------------------
    # Get player's games
    # -------------------------

    response = player_games_table.query(

        KeyConditionExpression=
            "user_id = :user_id",

        ExpressionAttributeValues={
            ":user_id": user_id
        }
    )

    player_games = response.get(
        "Items",
        []
    )


    return render_template(

        "profile.html",

        user=user,

        player_games=player_games
    )
@app.route(
    "/profile/add-game",
    methods=["GET", "POST"]
)
def add_game():

    if "user_id" not in session:

        flash(
            "Please log in first."
        )

        return redirect(
            url_for("login")
        )


    games_table = get_table(
        app.config["GAMES_TABLE"]
    )

    player_games_table = get_table(
        app.config["PLAYER_GAMES_TABLE"]
    )


    # -------------------------
    # Get available games
    # -------------------------

    games_response = games_table.scan()

    games = games_response.get(
        "Items",
        []
    )


    # -------------------------
    # GET
    # -------------------------

    if request.method == "GET":

        return render_template(

            "add_game.html",

            games=games
        )


    # -------------------------
    # POST
    # -------------------------

    user_id = session["user_id"]

    game_id = request.form.get(
        "game_id",
        ""
    ).strip()

    rank = request.form.get(
        "rank",
        ""
    ).strip()

    role = request.form.get(
        "role",
        ""
    ).strip()

    availability = request.form.get(
        "availability",
        ""
    ).strip()


    if (
        not game_id
        or not rank
        or not role
        or not availability
    ):

        flash(
            "Please complete all fields."
        )

        return redirect(
            url_for("add_game")
        )


    # Find selected game

    selected_game = None

    for game in games:

        if game["game_id"] == game_id:

            selected_game = game

            break


    if not selected_game:

        flash(
            "Invalid game selected."
        )

        return redirect(
            url_for("add_game")
        )


    # Save player game

    player_games_table.put_item(

        Item={

            "user_id": user_id,

            "game_id": game_id,

            "game_name":
                selected_game["game_name"],

            "rank": rank,

            "role": role,

            "availability":
                availability
        }
    )


    flash(
        "Game added successfully."
    )

    return redirect(
        url_for("profile")
    )
@app.route("/find-teammates")
def find_teammates():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)

    # Get current user
    user_response = users_table.get_item(
        Key={"user_id": user_id}
    )

    current_user = user_response.get("Item")

    if not current_user:
        flash("User not found.", "danger")
        return redirect(url_for("dashboard"))

    # Get games
    games_response = games_table.scan()
    games = games_response.get("Items", [])

    selected_game_id = request.args.get("game_id")

    recommendations = []

    if selected_game_id:

        # Get the current user's information for this game
        current_game_response = player_games_table.get_item(
            Key={
                "user_id": user_id,
                "game_id": selected_game_id
            }
        )

        current_game = current_game_response.get("Item")

        if current_game:

            current_player = {
                "region": current_user.get("region", ""),
                "rank": current_game.get("rank", ""),
                "role": current_game.get("role", ""),
                "availability": current_game.get(
                    "availability", ""
                )
            }

            # Query all players who play this game
            response = player_games_table.query(
                IndexName="game-index",
                KeyConditionExpression=Key(
                    "game_id"
                ).eq(selected_game_id)
            )

            candidates = response.get("Items", [])

            for candidate_game in candidates:

                candidate_id = candidate_game.get("user_id")

                # Don't recommend yourself
                if candidate_id == user_id:
                    continue

                # Get candidate's profile
                candidate_response = users_table.get_item(
                    Key={
                        "user_id": candidate_id
                    }
                )

                candidate_user = candidate_response.get("Item")

                if not candidate_user:
                    continue

                candidate = {
                    "user_id": candidate_id,
                    "username": candidate_user.get(
                        "username", "Unknown"
                    ),
                    "region": candidate_user.get(
                        "region", ""
                    ),
                    "bio": candidate_user.get(
                        "bio", ""
                    ),
                    "rank": candidate_game.get(
                        "rank", ""
                    ),
                    "role": candidate_game.get(
                        "role", ""
                    ),
                    "availability": candidate_game.get(
                        "availability", ""
                    ),
                    "game_name": candidate_game.get(
                        "game_name", ""
                    )
                }

                candidate["score"] = calculate_match_score(
                    current_player,
                    candidate
                )

                recommendations.append(candidate)

            # Highest score first
            recommendations.sort(
                key=lambda x: x["score"],
                reverse=True
            )

        else:
            flash(
                "You have not added this game to your profile yet.",
                "warning"
            )

    return render_template(
        "find_teammates.html",
        games=games,
        recommendations=recommendations,
        selected_game_id=selected_game_id
    )
@app.route("/invite/<receiver_id>/<game_id>", methods=["POST"])
def invite_player(receiver_id, game_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    sender_id = session["user_id"]

    # Prevent inviting yourself
    if sender_id == receiver_id:
        flash("You cannot invite yourself.", "danger")
        return redirect(url_for("find_teammates"))

    invitations_table = get_table(Config.INVITATIONS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)

    # Get sender
    sender_response = users_table.get_item(
        Key={"user_id": sender_id}
    )

    sender = sender_response.get("Item")

    # Get receiver
    receiver_response = users_table.get_item(
        Key={"user_id": receiver_id}
    )

    receiver = receiver_response.get("Item")

    if not sender or not receiver:
        flash("User not found.", "danger")
        return redirect(url_for("find_teammates"))

    # Get game
    game_response = games_table.get_item(
        Key={"game_id": game_id}
    )

    game = game_response.get("Item")

    if not game:
        flash("Game not found.", "danger")
        return redirect(url_for("find_teammates"))

    invitation_id = str(uuid.uuid4())

    invitation = {
        "receiver_id": receiver_id,
        "invitation_id": invitation_id,
        "sender_id": sender_id,
        "sender_username": sender.get("username"),
        "game_id": game_id,
        "game_name": game.get("game_name"),
        "status": "pending",
        "created_at": datetime.utcnow().isoformat()
    }

    invitations_table.put_item(
        Item=invitation
    )

    flash("Invitation sent successfully!", "success")

    return redirect(
        url_for(
            "find_teammates",
            game_id=game_id
        )
    )
@app.route("/notifications")
def notifications():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    invitations_table = get_table(
        Config.INVITATIONS_TABLE
    )

    response = invitations_table.query(
        KeyConditionExpression=Key(
            "receiver_id"
        ).eq(user_id)
    )

    invitations = response.get("Items", [])

    invitations.sort(
        key=lambda x: x.get("created_at", ""),
        reverse=True
    )

    return render_template(
        "notifications.html",
        invitations=invitations
    )
@app.route("/respond-invitation/<invitation_id>", methods=["POST"])
def respond_invitation(invitation_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    response = request.form.get("response")

    if response not in ["accepted", "rejected"]:
        flash("Invalid response.", "danger")
        return redirect(url_for("notifications"))

    invitations_table = get_table(
        Config.INVITATIONS_TABLE
    )

    # Get the invitation
    invitation_response = invitations_table.get_item(
        Key={
            "receiver_id": user_id,
            "invitation_id": invitation_id
        }
    )

    invitation = invitation_response.get("Item")

    if not invitation:
        flash("Invitation not found.", "danger")
        return redirect(url_for("notifications"))

    # Make sure it is still pending
    if invitation.get("status") != "pending":
        flash("This invitation has already been processed.", "warning")
        return redirect(url_for("notifications"))

    # --------------------------------
    # REJECT
    # --------------------------------

    if response == "rejected":

        invitations_table.update_item(
            Key={
                "receiver_id": user_id,
                "invitation_id": invitation_id
            },
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={
                "#status": "status"
            },
            ExpressionAttributeValues={
                ":status": "rejected"
            }
        )

        flash("Invitation rejected.", "info")

        return redirect(url_for("notifications"))

    # --------------------------------
    # ACCEPT
    # --------------------------------

    groups_table = get_table(
        Config.GROUPS_TABLE
    )

    members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    group_id = str(uuid.uuid4())

    group = {
        "group_id": group_id,
        "owner_id": invitation["sender_id"],
        "game_id": invitation["game_id"],
        "group_name": (
            invitation["sender_username"]
            + "'s "
            + invitation["game_name"]
            + " Team"
        ),
        "created_at": datetime.utcnow().isoformat()
    }

    # Create group
    groups_table.put_item(
        Item=group
    )

    # Add invitation sender
    members_table.put_item(
        Item={
            "group_id": group_id,
            "user_id": invitation["sender_id"],
            "role": "owner",
            "joined_at": datetime.utcnow().isoformat()
        }
    )

    # Add invitation receiver
    members_table.put_item(
        Item={
            "group_id": group_id,
            "user_id": user_id,
            "role": "member",
            "joined_at": datetime.utcnow().isoformat()
        }
    )

    # Update invitation
    invitations_table.update_item(
        Key={
            "receiver_id": user_id,
            "invitation_id": invitation_id
        },
        UpdateExpression="SET #status = :status",
        ExpressionAttributeNames={
            "#status": "status"
        },
        ExpressionAttributeValues={
            ":status": "accepted"
        }
    )

    flash("Invitation accepted! Your group has been created.", "success")

    return redirect(url_for("notifications"))

@app.route("/groups")
def groups():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    groups_table = get_table(
        Config.GROUPS_TABLE
    )

    games_table = get_table(
        Config.GAMES_TABLE
    )

    # Find all groups that the current user belongs to
    members_response = members_table.query(
        IndexName="user-index",
        KeyConditionExpression=Key(
            "user_id"
        ).eq(user_id)
    )

    memberships = members_response.get("Items", [])

    user_groups = []

    for membership in memberships:

        group_id = membership.get("group_id")

        group_response = groups_table.get_item(
            Key={
                "group_id": group_id
            }
        )

        group = group_response.get("Item")

        if not group:
            continue

        # Get game name
        game_name = "Unknown"

        game_id = group.get("game_id")

        if game_id:
            game_response = games_table.get_item(
                Key={
                    "game_id": game_id
                }
            )

            game = game_response.get("Item")

            if game:
                game_name = game.get(
                    "game_name",
                    "Unknown"
                )

        group["game_name"] = game_name
        group["member_role"] = membership.get(
            "role",
            "member"
        )

        user_groups.append(group)

    return render_template(
        "groups.html",
        groups=user_groups
    )

@app.route("/group/<group_id>")
def group_details(group_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)

    # --------------------------------
    # Get group
    # --------------------------------

    group_response = groups_table.get_item(
        Key={"group_id": group_id}
    )

    group = group_response.get("Item")

    if not group:
        flash("Group not found.", "danger")
        return redirect(url_for("groups"))

    # --------------------------------
    # Check current user is a member
    # --------------------------------

    membership_response = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": user_id
        }
    )

    membership = membership_response.get("Item")

    if not membership:
        flash(
            "You are not a member of this group.",
            "danger"
        )
        return redirect(url_for("groups"))

    # --------------------------------
    # Get game name
    # --------------------------------

    game_name = "Unknown"

    if group.get("game_id"):

        game_response = games_table.get_item(
            Key={
                "game_id": group["game_id"]
            }
        )

        game = game_response.get("Item")

        if game:
            game_name = game.get(
                "game_name",
                "Unknown"
            )

    group["game_name"] = game_name

    # --------------------------------
    # Get group members
    # --------------------------------

    members_response = members_table.query(
        KeyConditionExpression=Key(
            "group_id"
        ).eq(group_id)
    )

    memberships = members_response.get(
        "Items",
        []
    )

    members = []

    for member in memberships:

        member_user_response = users_table.get_item(
            Key={
                "user_id": member["user_id"]
            }
        )

        member_user = member_user_response.get(
            "Item"
        )

        if member_user:

            members.append({
                "user_id": member["user_id"],
                "username": member_user.get(
                    "username",
                    "Unknown"
                ),
                "region": member_user.get(
                    "region",
                    ""
                ),
                "role": member.get(
                    "role",
                    "member"
                )
            })

    # --------------------------------
    # Get group gaming sessions
    # --------------------------------

    sessions_response = sessions_table.query(
        IndexName="group-session-index",
        KeyConditionExpression=Key(
            "group_id"
        ).eq(group_id)
    )

    gaming_sessions = sessions_response.get(
        "Items",
        []
    )

    gaming_sessions.sort(
        key=lambda x: x.get(
            "session_time",
            ""
        )
    )

    return render_template(
        "group_details.html",
        group=group,
        members=members,
        gaming_sessions=gaming_sessions,
        current_user_id=user_id
    )

@app.route("/sessions")
def sessions():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    sessions_table = get_table(
        Config.SESSIONS_TABLE
    )

    members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    groups_table = get_table(
        Config.GROUPS_TABLE
    )

    # Find groups the current user belongs to
    membership_response = members_table.query(
        IndexName="user-index",
        KeyConditionExpression=Key(
            "user_id"
        ).eq(user_id)
    )

    memberships = membership_response.get(
        "Items",
        []
    )

    group_ids = [
        membership["group_id"]
        for membership in memberships
    ]

    gaming_sessions = []

    # Find sessions for each group
    for group_id in group_ids:

        response = sessions_table.query(
            IndexName="group-session-index",
            KeyConditionExpression=Key(
                "group_id"
            ).eq(group_id)
        )

        group_sessions = response.get(
            "Items",
            []
        )

        for gaming_session in group_sessions:

            group_response = groups_table.get_item(
                Key={
                    "group_id": group_id
                }
            )

            group = group_response.get("Item")

            if group:
                gaming_session["group_name"] = group.get(
                    "group_name",
                    "Unknown Group"
                )

            gaming_sessions.append(
                gaming_session
            )

    # Sort by session time
    gaming_sessions.sort(
        key=lambda x: x.get(
            "session_time",
            ""
        )
    )

    return render_template(
        "sessions.html",
        sessions=gaming_sessions
    )

@app.route("/create-session", methods=["GET", "POST"])
def create_session():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    groups_table = get_table(
        Config.GROUPS_TABLE
    )

    sessions_table = get_table(
        Config.SESSIONS_TABLE
    )

    # Get groups belonging to the user
    membership_response = members_table.query(
        IndexName="user-index",
        KeyConditionExpression=Key(
            "user_id"
        ).eq(user_id)
    )

    memberships = membership_response.get(
        "Items",
        []
    )

    groups = []

    for membership in memberships:

        group_response = groups_table.get_item(
            Key={
                "group_id": membership["group_id"]
            }
        )

        group = group_response.get("Item")

        if group:
            groups.append(group)

    # Group passed from Group Details
    selected_group_id = request.args.get("group_id")

    if request.method == "POST":

        group_id = request.form.get("group_id")
        session_name = request.form.get("session_name")
        session_time = request.form.get("session_time")
        description = request.form.get("description")

        # Verify membership
        valid_group = False

        for group in groups:

            if group["group_id"] == group_id:
                valid_group = True
                break

        if not valid_group:

            flash(
                "You are not a member of this group.",
                "danger"
            )

            return redirect(
                url_for("create_session")
            )

        session_id = str(uuid.uuid4())

        gaming_session = {
            "session_id": session_id,
            "group_id": group_id,
            "session_name": session_name,
            "session_time": session_time,
            "description": description,
            "created_by": user_id,
            "created_at": datetime.utcnow().isoformat()
        }

        sessions_table.put_item(
            Item=gaming_session
        )

        # Automatically join creator
        session_members_table = get_table(
            Config.SESSION_MEMBERS_TABLE
        )

        session_members_table.put_item(
            Item={
                "session_id": session_id,
                "user_id": user_id,
                "joined_at": datetime.utcnow().isoformat()
            }
        )

        flash(
            "Gaming session created successfully!",
            "success"
        )

        return redirect(
            url_for(
                "group_details",
                group_id=group_id
            )
        )

    return render_template(
        "create_session.html",
        groups=groups,
        selected_group_id=selected_group_id
    )

@app.route("/join-session/<session_id>", methods=["POST"])
def join_session(session_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    sessions_table = get_table(
        Config.SESSIONS_TABLE
    )

    members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    session_members_table = get_table(
        Config.SESSION_MEMBERS_TABLE
    )

    # Get session
    session_response = sessions_table.get_item(
        Key={
            "session_id": session_id
        }
    )

    gaming_session = session_response.get("Item")

    if not gaming_session:

        flash(
            "Gaming session not found.",
            "danger"
        )

        return redirect(
            url_for("sessions")
        )

    group_id = gaming_session["group_id"]

    # Verify user belongs to the group
    membership_response = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": user_id
        }
    )

    membership = membership_response.get("Item")

    if not membership:

        flash(
            "You must be a group member to join this session.",
            "danger"
        )

        return redirect(
            url_for("sessions")
        )

    # Check whether already joined
    existing_response = session_members_table.get_item(
        Key={
            "session_id": session_id,
            "user_id": user_id
        }
    )

    if existing_response.get("Item"):

        flash(
            "You have already joined this session.",
            "info"
        )

        return redirect(
            url_for("sessions")
        )

    # Add member
    session_members_table.put_item(
        Item={
            "session_id": session_id,
            "user_id": user_id,
            "joined_at": datetime.utcnow().isoformat()
        }
    )

    flash(
        "You joined the gaming session!",
        "success"
    )

    return redirect(
        url_for("sessions")
    )

@app.route("/session/<session_id>")
def session_details(session_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    sessions_table = get_table(Config.SESSIONS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    session_members_table = get_table(
        Config.SESSION_MEMBERS_TABLE
    )
    users_table = get_table(Config.USERS_TABLE)

    # Get session
    session_response = sessions_table.get_item(
        Key={
            "session_id": session_id
        }
    )

    gaming_session = session_response.get("Item")

    if not gaming_session:
        flash(
            "Gaming session not found.",
            "danger"
        )
        return redirect(url_for("sessions"))

    group_id = gaming_session["group_id"]

    # Check that current user belongs to the group
    membership_response = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": user_id
        }
    )

    membership = membership_response.get("Item")

    if not membership:
        flash(
            "You are not a member of this group.",
            "danger"
        )
        return redirect(url_for("sessions"))

    # Get group
    group_response = groups_table.get_item(
        Key={
            "group_id": group_id
        }
    )

    group = group_response.get("Item")

    if not group:
        flash(
            "Group not found.",
            "danger"
        )
        return redirect(url_for("groups"))

    # Get session members
    members_response = session_members_table.query(
        KeyConditionExpression=Key(
            "session_id"
        ).eq(session_id)
    )

    session_members = members_response.get("Items", [])

    members = []

    for session_member in session_members:

        member_user_id = session_member["user_id"]

        user_response = users_table.get_item(
            Key={
                "user_id": member_user_id
            }
        )

        member_user = user_response.get("Item")

        if member_user:
            members.append({
                "user_id": member_user_id,
                "username": member_user.get(
                    "username",
                    "Unknown"
                ),
                "region": member_user.get(
                    "region",
                    ""
                ),
                "joined_at": session_member.get(
                    "joined_at",
                    ""
                )
            })
    return render_template(
        "session_details.html",
        gaming_session=gaming_session,
        group=group,
        members=members,
        current_user_id=user_id
    )

@app.route("/admin")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    invitations_table = get_table(Config.INVITATIONS_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    group_members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )

    # Check admin
    response = users_table.get_item(
        Key={"user_id": user_id}
    )

    current_user = response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash(
            "You do not have permission to access the admin dashboard.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    # Basic counts
    users_count = users_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    games_count = games_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    groups_count = groups_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    sessions_count = sessions_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    # Player-game relationships
    player_games_count = player_games_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    # Group memberships
    memberships_count = group_members_table.scan(
        Select="COUNT"
    ).get("Count", 0)

    # Invitations
    invitations_response = invitations_table.scan()

    invitations = invitations_response.get(
        "Items",
        []
    )

    pending_invitations_count = sum(
        1
        for invitation in invitations
        if invitation.get("status") == "pending"
    )

    accepted_invitations_count = sum(
        1
        for invitation in invitations
        if invitation.get("status") == "accepted"
    )

    rejected_invitations_count = sum(
        1
        for invitation in invitations
        if invitation.get("status") == "rejected"
    )

    return render_template(
        "admin_dashboard.html",

        users_count=users_count,
        games_count=games_count,
        groups_count=groups_count,
        sessions_count=sessions_count,

        player_games_count=player_games_count,
        memberships_count=memberships_count,

        pending_invitations_count=
            pending_invitations_count,

        accepted_invitations_count=
            accepted_invitations_count,

        rejected_invitations_count=
            rejected_invitations_count
    )

@app.route("/admin/users")
def admin_users():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)

    # Check current user
    response = users_table.get_item(
        Key={"user_id": user_id}
    )

    current_user = response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash(
            "You do not have permission to access this page.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    # Get all users
    users_response = users_table.scan()

    users = users_response.get("Items", [])

    # Do not display the admin's own account as removable
    users.sort(
        key=lambda x: x.get("username", "").lower()
    )

    return render_template(
        "admin_users.html",
        users=users,
        current_user_id=user_id
    )

@app.route(
    "/admin/users/delete/<target_user_id>",
    methods=["POST"]
)
def delete_user(target_user_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    admin_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    player_games_table = get_table(
        Config.PLAYER_GAMES_TABLE
    )
    group_members_table = get_table(
        Config.GROUP_MEMBERS_TABLE
    )
    invitations_table = get_table(
        Config.INVITATIONS_TABLE
    )
    session_members_table = get_table(
        Config.SESSION_MEMBERS_TABLE
    )

    # Check admin
    admin_response = users_table.get_item(
        Key={"user_id": admin_id}
    )

    admin = admin_response.get("Item")

    if not admin or admin.get("role") != "admin":
        flash(
            "You do not have permission to perform this action.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    # Prevent deleting yourself
    if target_user_id == admin_id:
        flash(
            "You cannot delete your own admin account.",
            "danger"
        )
        return redirect(url_for("admin_users"))

    # Check user exists
    target_response = users_table.get_item(
        Key={"user_id": target_user_id}
    )

    target_user = target_response.get("Item")

    if not target_user:
        flash(
            "User not found.",
            "danger"
        )
        return redirect(url_for("admin_users"))

    # ------------------------------------------------
    # Delete player's game profiles
    # ------------------------------------------------

    player_games_response = player_games_table.query(
        KeyConditionExpression=Key(
            "user_id"
        ).eq(target_user_id)
    )

    for player_game in player_games_response.get(
        "Items",
        []
    ):

        player_games_table.delete_item(
            Key={
                "user_id": target_user_id,
                "game_id": player_game["game_id"]
            }
        )

    # ------------------------------------------------
    # Delete group memberships
    # ------------------------------------------------

    memberships_response = group_members_table.query(
        IndexName="user-index",
        KeyConditionExpression=Key(
            "user_id"
        ).eq(target_user_id)
    )

    for membership in memberships_response.get(
        "Items",
        []
    ):

        group_members_table.delete_item(
            Key={
                "group_id": membership["group_id"],
                "user_id": target_user_id
            }
        )

    # ------------------------------------------------
    # Delete invitations received
    # ------------------------------------------------

    invitations_response = invitations_table.query(
        KeyConditionExpression=Key(
            "receiver_id"
        ).eq(target_user_id)
    )

    for invitation in invitations_response.get(
        "Items",
        []
    ):

        invitations_table.delete_item(
            Key={
                "receiver_id": target_user_id,
                "invitation_id": invitation["invitation_id"]
            }
        )

    # ------------------------------------------------
    # Delete invitations sent
    # ------------------------------------------------

    sent_invitations_response = invitations_table.scan(
        FilterExpression=Attr(
            "sender_id"
        ).eq(target_user_id)
    )

    for invitation in sent_invitations_response.get(
        "Items",
        []
    ):

        invitations_table.delete_item(
            Key={
                "receiver_id": invitation["receiver_id"],
                "invitation_id": invitation["invitation_id"]
            }
        )

    # ------------------------------------------------
    # Delete session memberships
    # ------------------------------------------------

    session_members_response = session_members_table.scan(
        FilterExpression=Attr(
            "user_id"
        ).eq(target_user_id)
    )

    for session_member in session_members_response.get(
        "Items",
        []
    ):

        session_members_table.delete_item(
            Key={
                "session_id": session_member["session_id"],
                "user_id": target_user_id
            }
        )

    # ------------------------------------------------
    # Delete user
    # ------------------------------------------------

    users_table.delete_item(
        Key={
            "user_id": target_user_id
        }
    )

    flash(
        f"User {target_user.get('username', '')} "
        "and related records were deleted.",
        "success"
    )

    return redirect(url_for("admin_users"))

@app.route("/admin/games")
def admin_games():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)

    # Check admin
    response = users_table.get_item(
        Key={"user_id": user_id}
    )

    current_user = response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash(
            "You do not have permission to access this page.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    # Get games
    games_response = games_table.scan()

    games = games_response.get("Items", [])

    games.sort(
        key=lambda x: x.get("game_name", "").lower()
    )

    return render_template(
        "admin_games.html",
        games=games
    )

@app.route("/admin/games/add", methods=["POST"])
def add_admin_game():

    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)

    # Check admin
    response = users_table.get_item(
        Key={"user_id": user_id}
    )

    current_user = response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash(
            "You do not have permission to perform this action.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    game_name = request.form.get("game_name", "").strip()
    genre = request.form.get("genre", "").strip()

    if not game_name or not genre:
        flash(
            "Game name and genre are required.",
            "danger"
        )
        return redirect(url_for("admin_games"))

    # Check whether game already exists
    existing_response = games_table.scan()

    existing_games = existing_response.get(
        "Items",
        []
    )

    for game in existing_games:

        if game.get("game_name", "").lower() == game_name.lower():

            flash(
                "This game is already exists.",
                "warning"
            )
            return redirect(url_for("admin_games"))

    game_id = str(uuid.uuid4())

    games_table.put_item(
        Item={
            "game_id": game_id,
            "game_name": game_name,
            "genre": genre
        }
    )

    flash(
        f"{game_name} was added successfully.",
        "success"
    )

    return redirect(url_for("admin_games"))

@app.route(
    "/admin/games/delete/<game_id>",
    methods=["POST"]
)
def delete_admin_game(game_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    admin_id = session["user_id"]

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    player_games_table = get_table(
        Config.PLAYER_GAMES_TABLE
    )

    # Check admin
    response = users_table.get_item(
        Key={"user_id": admin_id}
    )

    current_user = response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash(
            "You do not have permission to perform this action.",
            "danger"
        )
        return redirect(url_for("dashboard"))

    # Check game exists
    game_response = games_table.get_item(
        Key={"game_id": game_id}
    )

    game = game_response.get("Item")

    if not game:
        flash(
            "Game not found.",
            "danger"
        )
        return redirect(url_for("admin_games"))

    # Check whether players are using this game
    player_games_response = player_games_table.query(
        IndexName="game-index",
        KeyConditionExpression=Key(
            "game_id"
        ).eq(game_id)
    )

    player_games = player_games_response.get(
        "Items",
        []
    )

    if player_games:

        flash(
            f"Cannot delete {game.get('game_name', 'this game')} "
            f"because {len(player_games)} player profile(s) "
            "are currently using it.",
            "warning"
        )

        return redirect(url_for("admin_games"))

    # Delete game
    games_table.delete_item(
        Key={
            "game_id": game_id
        }
    )

    flash(
        f"{game.get('game_name', 'Game')} was deleted successfully.",
        "success"
    )

    return redirect(url_for("admin_games"))

@app.route("/api/lambda/users", methods=["GET"])
def lambda_get_users():
    try:
        users_table = get_table(Config.USERS_TABLE)

        result = users_table.scan(
            ProjectionExpression="user_id, username, #email, #region",
            ExpressionAttributeNames={
                "#email": "email",
                "#region": "region"
            }
        )

        return jsonify({
            "users": result.get("Items", [])
        }), 200

    except Exception as error:
        print("Lambda API error:", str(error))

        return jsonify({
            "message": "Unable to retrieve users"
        }), 500

@app.route("/group/<group_id>/add-member", methods=["POST"])
def add_group_member(group_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user_id = session["user_id"]

    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)

    # Get group
    group_response = groups_table.get_item(
        Key={"group_id": group_id}
    )

    group = group_response.get("Item")

    if not group:
        flash("Group not found.", "danger")
        return redirect(url_for("groups"))

    # Only owner can add teammates
    if group.get("owner_id") != current_user_id:
        flash(
            "Only the group owner can add teammates.",
            "danger"
        )
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    target_user_id = request.form.get("user_id")

    if not target_user_id:
        flash("Please select a player.", "warning")
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    # Prevent adding yourself
    if target_user_id == current_user_id:
        flash(
            "You cannot add yourself to your own group.",
            "warning"
        )
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    # Check target user exists
    user_response = users_table.get_item(
        Key={"user_id": target_user_id}
    )

    target_user = user_response.get("Item")

    if not target_user:
        flash("Player not found.", "danger")
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    # Check whether already a member
    existing_member = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": target_user_id
        }
    )

    if existing_member.get("Item"):
        flash(
            f"{target_user.get('username')} is already in the group.",
            "warning"
        )
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    # Add player
    members_table.put_item(
        Item={
            "group_id": group_id,
            "user_id": target_user_id,
            "username": target_user.get("username"),
            "joined_at": datetime.utcnow().isoformat()
        }
    )

    flash(
        f"{target_user.get('username')} has been added to the group.",
        "success"
    )

    return redirect(
        url_for("group_details", group_id=group_id)
    )

@app.route("/group/<group_id>/search-players")
def search_group_players(group_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user_id = session["user_id"]

    groups_table = get_table(Config.GROUPS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)

    # Check group
    group_response = groups_table.get_item(
        Key={"group_id": group_id}
    )

    group = group_response.get("Item")

    if not group:
        flash("Group not found.", "danger")
        return redirect(url_for("groups"))

    # Only owner can search/add
    if group.get("owner_id") != current_user_id:
        flash(
            "Only the group owner can add teammates.",
            "danger"
        )
        return redirect(
            url_for("group_details", group_id=group_id)
        )

    search = request.args.get("search", "").strip()

    players = []

    if search:

        response = users_table.query(
            IndexName="username-index",
            KeyConditionExpression="username = :username",
            ExpressionAttributeValues={
                ":username": search
            }
        )

        players = response.get("Items", [])

    return render_template(
        "search_group_players.html",
        group=group,
        players=players,
        search=search
    )

# =========================
# LOGOUT
# =========================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out."
    )

    return redirect(
        url_for("login")
    )


# =========================
# RUN APPLICATION
# =========================

if __name__ == "__main__":

    app.run(
        debug=True
    )