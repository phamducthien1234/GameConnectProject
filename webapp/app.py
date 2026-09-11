from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from boto3.dynamodb.conditions import Key, Attr
from services.s3 import (upload_profile_image, create_profile_image_url,save_analytics_event,read_json_folder)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from services.dynamodb import get_table
from services.matching import calculate_match_score
import uuid
from datetime import datetime, timezone, timedelta
import random
import requests

app = Flask(__name__)
app.config.from_object(Config)

@app.template_filter('datetime')
def format_datetime(value):
    if not value:
        return ''
    try:
        dt = datetime.fromisoformat(value)
        vietnam_time = dt.astimezone(timezone(timedelta(hours=7)))
        return vietnam_time.strftime('%H:%M:%S %Y-%m-%d')
    except (ValueError, TypeError):
        return value

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test-dynamodb')
def test_dynamodb():
    try:
        table = get_table(app.config['USERS_TABLE'])
        response = table.scan(Limit=1)
        return {'status': 'success', 'message': 'Flask is connected to GameConnectUsers', 'table': app.config['USERS_TABLE'], 'region': app.config['AWS_REGION'], 'items_found': response['Count']}
    except Exception as e:
        return ({'status': 'error', 'message': str(e)}, 500)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    region = request.form.get('region', '').strip()
    if not username or not email or (not password) or (not region):
        flash('Please complete all fields.')
        return redirect(url_for('register'))
    if len(password) < 8:
        flash('Password must be at least 8 characters.')
        return redirect(url_for('register'))
    users_table = get_table(app.config['USERS_TABLE'])
    username_response = users_table.query(IndexName='username-index', KeyConditionExpression='username = :username', ExpressionAttributeValues={':username': username})
    if username_response['Items']:
        flash('Username is already taken.')
        return redirect(url_for('register'))
    email_response = users_table.query(IndexName='email-index', KeyConditionExpression='email = :email', ExpressionAttributeValues={':email': email})
    if email_response['Items']:
        flash('Email is already registered.')
        return redirect(url_for('register'))
    user_id = str(uuid.uuid4())
    password_hash = generate_password_hash(password)
    user = {'user_id': user_id, 'username': username, 'email': email, 'password_hash': password_hash, 'role': 'player', 'region': region, 'bio': '', 'profile_image_url': '', 'created_at': datetime.now(timezone.utc).isoformat()}
    users_table.put_item(Item=user, ConditionExpression='attribute_not_exists(user_id)')
    flash('Registration successful. Please log in.')
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    if not username or not password:
        flash('Please enter username and password.')
        return redirect(url_for('login'))
    users_table = get_table(app.config['USERS_TABLE'])
    response = users_table.query(IndexName='username-index', KeyConditionExpression='username = :username', ExpressionAttributeValues={':username': username})
    users = response.get('Items', [])
    if not users:
        flash('Invalid username or password.')
        return redirect(url_for('login'))
    user = users[0]
    if not check_password_hash(user['password_hash'], password):
        flash('Invalid username or password.')
        return redirect(url_for('login'))
    session['user_id'] = user['user_id']
    session['username'] = user['username']
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))

    users_table = get_table(app.config['USERS_TABLE'])

    response = users_table.get_item(
        Key={'user_id': session['user_id']}
    )

    user = response.get('Item')

    if not user:
        session.clear()
        flash('User account could not be found.')
        return redirect(url_for('login'))

    user["profile_image_url"] = None

    if user.get("profile_image_key"):
        try:
            user["profile_image_url"] = create_profile_image_url(
                user["profile_image_key"]
            )
        except Exception as error:
            print("Dashboard profile image error:", str(error))

    return render_template(
        'dashboard.html',
        user=user
    )

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        flash("Please log in first.")
        return redirect(url_for("login"))

    users_table = get_table(Config.USERS_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    user_id = session["user_id"]

    if request.method == "POST":
        region = request.form.get("region", "").strip()
        bio = request.form.get("bio", "").strip()
        profile_image = request.files.get("profile_image")

        update_expression = "SET #region = :region, bio = :bio"
        expression_names = {"#region": "region"}
        expression_values = {
            ":region": region,
            ":bio": bio
        }

        if profile_image and profile_image.filename:
            allowed_extensions = {"jpg", "jpeg", "png", "webp"}

            if "." not in profile_image.filename:
                flash("Invalid image file.")
                return redirect(url_for("profile"))

            extension = profile_image.filename.rsplit(".", 1)[-1].lower()

            if extension not in allowed_extensions:
                flash("Profile image must be JPG, JPEG, PNG or WEBP.")
                return redirect(url_for("profile"))

            try:
                object_key = upload_profile_image(
                    profile_image,
                    user_id
                )

                update_expression += ", profile_image_key = :image_key"
                expression_values[":image_key"] = object_key

            except Exception as error:
                print("S3 upload error:", str(error))
                flash("Unable to upload profile image.")
                return redirect(url_for("profile"))

        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_names,
            ExpressionAttributeValues=expression_values
        )

        flash("Profile updated successfully.")

        return redirect(url_for("profile"))

    response = users_table.get_item(
        Key={"user_id": user_id}
    )

    user = response.get("Item")

    if not user:
        session.clear()
        return redirect(url_for("login"))

    user["profile_image_url"] = None

    if user.get("profile_image_key"):
        try:
            user["profile_image_url"] = create_profile_image_url(
                user["profile_image_key"]
            )
        except Exception as error:
            print("S3 URL error:", str(error))

    response = player_games_table.query(
        KeyConditionExpression=Key("user_id").eq(user_id)
    )

    player_games = response.get("Items", [])

    return render_template(
        "profile.html",
        user=user,
        player_games=player_games
    )

@app.route('/profile/add-game', methods=['GET', 'POST'])
def add_game():
    if 'user_id' not in session:
        flash('Please log in first.')
        return redirect(url_for('login'))
    games_table = get_table(app.config['GAMES_TABLE'])
    player_games_table = get_table(app.config['PLAYER_GAMES_TABLE'])
    games = games_table.scan().get('Items', [])
    games.sort(key=lambda game: game.get('game_name', '').lower())
    if request.method == 'GET':
        return render_template('add_game.html', games=games)
    user_id = session['user_id']
    game_id = request.form.get('game_id', '').strip()
    rank = request.form.get('rank', '').strip()
    role = request.form.get('role', '').strip()
    availability = request.form.get('availability', '').strip()
    riot_game_name = request.form.get('riot_game_name', '').strip()
    riot_tag_line = request.form.get('riot_tag_line', '').strip()
    riot_puuid = request.form.get('riot_puuid', '').strip()
    riot_rank = request.form.get('riot_rank', '').strip()
    if not game_id or not rank or (not role) or (not availability):
        flash('Please complete all fields.')
        return redirect(url_for('add_game'))
    selected_game = next((game for game in games if game.get('game_id') == game_id), None)
    if not selected_game:
        flash('Invalid game selected.')
        return redirect(url_for('add_game'))
    existing = player_games_table.get_item(Key={'user_id': user_id, 'game_id': game_id}).get('Item')
    if existing:
        flash('You have already added this game to your profile.')
        return redirect(url_for('profile'))
    player_game = {'user_id': user_id, 'game_id': game_id, 'game_name': selected_game['game_name'], 'rank': rank, 'role': role, 'availability': availability}
    if selected_game.get('game_name', '').lower() == 'league of legends':
        if not riot_game_name or not riot_tag_line or (not riot_puuid):
            flash('Please fetch and verify your Riot profile before adding League of Legends.')
            return redirect(url_for('add_game'))
        player_game.update({'riot_game_name': riot_game_name, 'riot_tag_line': riot_tag_line, 'riot_puuid': riot_puuid, 'riot_rank': riot_rank or rank, 'riot_verified': True})
        if riot_rank:
            player_game['rank'] = riot_rank
    player_games_table.put_item(Item=player_game, ConditionExpression='attribute_not_exists(user_id) AND attribute_not_exists(game_id)')
    flash('Game added successfully.')
    return redirect(url_for('profile'))

@app.route('/find-teammates')
def find_teammates():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)

    user_response = users_table.get_item(
        Key={'user_id': user_id}
    )

    current_user = user_response.get('Item')

    if not current_user:
        session.clear()
        return redirect(url_for('login'))

    games_response = games_table.scan()
    games = games_response.get('Items', [])

    games.sort(
        key=lambda game: game.get('game_name', '').lower()
    )

    owned_groups_response = groups_table.query(
        IndexName='owner-index',
        KeyConditionExpression=Key('owner_id').eq(user_id)
    )

    owned_groups = owned_groups_response.get('Items', [])

    selected_game_id = request.args.get('game_id', '')

    recommendations = []
    random_teammates = []

    users_response = users_table.scan()
    all_users = users_response.get('Items', [])

    possible_random_users = [
        user
        for user in all_users
        if user.get('user_id') != user_id
        and user.get('role') != 'admin'
    ]

    if possible_random_users:
        sample_size = min(
            6,
            len(possible_random_users)
        )

        selected_random_users = random.sample(
            possible_random_users,
            sample_size
        )

        for random_user in selected_random_users:

            random_user_id = random_user.get('user_id')

            player_games_response = player_games_table.query(
                KeyConditionExpression=Key('user_id').eq(
                    random_user_id
                )
            )

            random_games = player_games_response.get(
                'Items',
                []
            )

            if random_games:
                random_game = random.choice(random_games)

                random_teammates.append({
                    'user_id': random_user_id,
                    'username': random_user.get(
                        'username',
                        'Unknown'
                    ),
                    'region': random_user.get(
                        'region',
                        ''
                    ),
                    'bio': random_user.get(
                        'bio',
                        ''
                    ),
                    'game_id': random_game.get(
                        'game_id',
                        ''
                    ),
                    'game_name': random_game.get(
                        'game_name',
                        'Unknown Game'
                    ),
                    'rank': random_game.get(
                        'rank',
                        ''
                    ),
                    'role': random_game.get(
                        'role',
                        ''
                    ),
                    'availability': random_game.get(
                        'availability',
                        ''
                    )
                })

    if selected_game_id:

        selected_game_response = games_table.get_item(
            Key={'game_id': selected_game_id}
        )

        selected_game = selected_game_response.get('Item')

        if not selected_game:
            flash('Selected game was not found.')
            return redirect(
                url_for('find_teammates')
            )

        game_name = selected_game.get(
            'game_name',
            ''
        )

        current_game_response = player_games_table.get_item(
            Key={
                'user_id': user_id,
                'game_id': selected_game_id
            }
        )

        current_game_profile = current_game_response.get(
            'Item'
        )

        if not current_game_profile:

            flash(
                'Please add this game to your profile first.'
            )

        else:

            current_player = {
                'user_id': user_id,
                'username': current_user.get(
                    'username',
                    ''
                ),
                'game_id': selected_game_id,
                'game_name': game_name,
                'rank': current_game_profile.get(
                    'rank',
                    ''
                ),
                'role': current_game_profile.get(
                    'role',
                    ''
                ),
                'region': current_user.get(
                    'region',
                    ''
                ),
                'availability': current_game_profile.get(
                    'availability',
                    ''
                ),
                'bio': current_user.get(
                    'bio',
                    ''
                )
            }

            candidates_response = player_games_table.query(
                IndexName='game-index',
                KeyConditionExpression=Key(
                    'game_id'
                ).eq(selected_game_id)
            )

            candidates = candidates_response.get(
                'Items',
                []
            )

            for candidate_game in candidates:

                candidate_user_id = candidate_game.get(
                    'user_id'
                )

                if candidate_user_id == user_id:
                    continue

                candidate_user_response = users_table.get_item(
                    Key={
                        'user_id': candidate_user_id
                    }
                )

                candidate_user = candidate_user_response.get(
                    'Item'
                )

                if not candidate_user:
                    continue

                candidate = {
                    'user_id': candidate_user_id,
                    'username': candidate_user.get(
                        'username',
                        ''
                    ),
                    'game_id': selected_game_id,
                    'game_name': candidate_game.get(
                        'game_name',
                        game_name
                    ),
                    'rank': candidate_game.get(
                        'rank',
                        ''
                    ),
                    'role': candidate_game.get(
                        'role',
                        ''
                    ),
                    'region': candidate_user.get(
                        'region',
                        ''
                    ),
                    'availability': candidate_game.get(
                        'availability',
                        ''
                    ),
                    'bio': candidate_user.get(
                        'bio',
                        ''
                    )
                }

                score = calculate_match_score(
                    current_player,
                    candidate
                )

                candidate['score'] = score

                recommendations.append(candidate)

            recommendations.sort(
                key=lambda player: player['score'],
                reverse=True
            )

            try:
                save_analytics_event(
                    'teammate_search',
                    user_id,
                    {
                        'game_id': selected_game_id,
                        'game_name': game_name,
                        'recommendation_count': len(
                            recommendations
                        )
                    }
                )

            except Exception as error:
                print(
                    'Analytics event error:',
                    str(error)
                )

    return render_template(
        'find_teammates.html',
        games=games,
        recommendations=recommendations,
        random_teammates=random_teammates,
        selected_game_id=selected_game_id,
        owned_groups=owned_groups
    )

@app.route("/invite/<receiver_id>/<game_id>", methods=["POST"])
def invite_player(receiver_id, game_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    sender_id = session["user_id"]

    if sender_id == receiver_id:
        flash("You cannot invite yourself.")
        return redirect(url_for("find_teammates", game_id=game_id))

    invitations_table = get_table(Config.INVITATIONS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)

    sender = users_table.get_item(
        Key={"user_id": sender_id}
    ).get("Item")

    receiver = users_table.get_item(
        Key={"user_id": receiver_id}
    ).get("Item")

    game = games_table.get_item(
        Key={"game_id": game_id}
    ).get("Item")

    if not sender or not receiver:
        flash("User not found.")
        return redirect(url_for("find_teammates", game_id=game_id))

    if not game:
        flash("Game not found.")
        return redirect(url_for("find_teammates", game_id=game_id))

    group_choice = request.form.get("group_choice", "").strip()
    new_group_name = request.form.get("new_group_name", "").strip()

    if not group_choice:
        flash("Please select a group.")
        return redirect(url_for("find_teammates", game_id=game_id))

    if group_choice == "new":
        if not new_group_name:
            flash("Please enter a new group name.")
            return redirect(url_for("find_teammates", game_id=game_id))

        group_id = str(uuid.uuid4())

        groups_table.put_item(
            Item={
                "group_id": group_id,
                "owner_id": sender_id,
                "game_id": game_id,
                "group_name": new_group_name,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        )

        members_table.put_item(
            Item={
                "group_id": group_id,
                "user_id": sender_id,
                "username": sender.get("username", ""),
                "role": "owner",
                "joined_at": datetime.now(timezone.utc).isoformat()
            }
        )

    else:
        group_id = group_choice

        group = groups_table.get_item(
            Key={"group_id": group_id}
        ).get("Item")

        if not group:
            flash("The selected group could not be found.")
            return redirect(
                url_for(
                    "find_teammates",
                    game_id=game_id
                )
            )

        if group.get("owner_id") != sender_id:
            flash("You can only invite players to a group that you own.")
            return redirect(
                url_for(
                    "find_teammates",
                    game_id=game_id
                )
            )

        if group.get("game_id") != game_id:
            flash("This group is linked to a different game.")
            return redirect(
                url_for(
                    "find_teammates",
                    game_id=game_id
                )
            )

    invitation_id = str(uuid.uuid4())

    invitations_table.put_item(
        Item={
            "receiver_id": receiver_id,
            "invitation_id": invitation_id,
            "sender_id": sender_id,
            "sender_username": sender.get("username", ""),
            "game_id": game_id,
            "game_name": game.get("game_name", ""),
            "group_id": group_id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
    )

    try:
        save_analytics_event(
            "invitation_sent",
            sender_id,
            {
                "receiver_id": receiver_id,
                "game_id": game_id,
                "game_name": game.get("game_name"),
                "group_id": group_id
            }
        )
    except Exception as error:
        print("Analytics event error:", str(error))

    flash(f"Invitation sent successfully to {receiver.get('username', 'player')}!")

    return redirect(
        url_for("find_teammates", game_id=game_id)
    )

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    invitations_table = get_table(Config.INVITATIONS_TABLE)
    response = invitations_table.query(KeyConditionExpression=Key('receiver_id').eq(user_id))
    invitations = response.get('Items', [])
    invitations.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('notifications.html', invitations=invitations)

@app.route('/respond-invitation/<invitation_id>', methods=['POST'])
def respond_invitation(invitation_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    response = request.form.get('response')

    if response not in ['accepted', 'rejected']:
        flash('Invalid response.')
        return redirect(url_for('notifications'))

    invitations_table = get_table(Config.INVITATIONS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)

    invitation = invitations_table.get_item(
        Key={'receiver_id': user_id, 'invitation_id': invitation_id}
    ).get('Item')

    if not invitation:
        flash('Invitation not found.')
        return redirect(url_for('notifications'))

    if invitation.get('status') != 'pending':
        flash('This invitation has already been processed.')
        return redirect(url_for('notifications'))

    if response == 'rejected':
        invitations_table.update_item(
            Key={'receiver_id': user_id, 'invitation_id': invitation_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'rejected'}
        )
        flash('Invitation rejected.')
        return redirect(url_for('notifications'))

    group_id = invitation.get('group_id')
    if not group_id:
        flash('This invitation does not contain a group.')
        return redirect(url_for('notifications'))

    group = groups_table.get_item(Key={'group_id': group_id}).get('Item')
    if not group:
        flash('The group for this invitation no longer exists.')
        return redirect(url_for('notifications'))

    existing_member = members_table.get_item(
        Key={'group_id': group_id, 'user_id': user_id}
    ).get('Item')

    if not existing_member:
        user = users_table.get_item(Key={'user_id': user_id}).get('Item')
        members_table.put_item(
            Item={
                'group_id': group_id,
                'user_id': user_id,
                'username': user.get('username', '') if user else '',
                'role': 'member',
                'joined_at': datetime.now(timezone.utc).isoformat()
            }
        )

    invitations_table.update_item(
        Key={'receiver_id': user_id, 'invitation_id': invitation_id},
        UpdateExpression='SET #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':status': 'accepted'}
    )

    flash('Invitation accepted! You have joined the group.')
    return redirect(url_for('group_details', group_id=group_id))

@app.route('/groups')
def groups():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    members_response = members_table.query(IndexName='user-index', KeyConditionExpression=Key('user_id').eq(user_id))
    memberships = members_response.get('Items', [])
    user_groups = []
    for membership in memberships:
        group_id = membership.get('group_id')
        group_response = groups_table.get_item(Key={'group_id': group_id})
        group = group_response.get('Item')
        if not group:
            continue
        game_name = 'Unknown'
        game_id = group.get('game_id')
        if game_id:
            game_response = games_table.get_item(Key={'game_id': game_id})
            game = game_response.get('Item')
            if game:
                game_name = game.get('game_name', 'Unknown')
        group['game_name'] = game_name
        group['member_role'] = membership.get('role', 'member')
        user_groups.append(group)
    return render_template('groups.html', groups=user_groups)

@app.route('/group/<group_id>')
def group_details(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)

    group_response = groups_table.get_item(
        Key={'group_id': group_id}
    )

    group = group_response.get('Item')

    if not group:
        flash('Group not found.')
        return redirect(url_for('groups'))

    membership_response = members_table.get_item(
        Key={
            'group_id': group_id,
            'user_id': user_id
        }
    )

    membership = membership_response.get('Item')

    if not membership:
        flash('You are not a member of this group.')
        return redirect(url_for('groups'))

    game_name = 'Unknown'

    if group.get('game_id'):
        game_response = games_table.get_item(
            Key={'game_id': group['game_id']}
        )

        game = game_response.get('Item')

        if game:
            game_name = game.get(
                'game_name',
                'Unknown'
            )

    group['game_name'] = game_name

    members_response = members_table.query(
        KeyConditionExpression=Key(
            'group_id'
        ).eq(group_id)
    )

    memberships = members_response.get('Items', [])

    owner = None
    members = []

    for member in memberships:
        member_user_response = users_table.get_item(
            Key={
                'user_id': member['user_id']
            }
        )

        member_user = member_user_response.get('Item')

        if not member_user:
            continue

        member_data = {
            'user_id': member['user_id'],
            'username': member_user.get(
                'username',
                'Unknown'
            ),
            'region': member_user.get(
                'region',
                ''
            ),
            'role': member.get(
                'role',
                'member'
            )
        }

        if member['user_id'] == group.get('owner_id'):
            owner = member_data
        else:
            members.append(member_data)

    sessions_response = sessions_table.query(
        IndexName='group-session-index',
        KeyConditionExpression=Key(
            'group_id'
        ).eq(group_id)
    )

    gaming_sessions = sessions_response.get(
        'Items',
        []
    )

    gaming_sessions.sort(
        key=lambda x: x.get(
            'session_time',
            ''
        )
    )

    return render_template(
        'group_details.html',
        group=group,
        owner=owner,
        members=members,
        gaming_sessions=gaming_sessions,
        current_user_id=user_id
    )

@app.route("/group/<group_id>/leave", methods=["POST"])
def leave_group(group_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]

    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)
    session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)

    group = groups_table.get_item(
        Key={"group_id": group_id}
    ).get("Item")

    if not group:
        flash("Group not found.")
        return redirect(url_for("groups"))

    membership = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": user_id
        }
    ).get("Item")

    if not membership:
        flash("You are not a member of this group.")
        return redirect(url_for("groups"))

    members_response = members_table.query(
        KeyConditionExpression=Key("group_id").eq(group_id)
    )

    memberships = members_response.get("Items", [])

    remaining_members = [
        member
        for member in memberships
        if member.get("user_id") != user_id
    ]

    is_owner = group.get("owner_id") == user_id

    if is_owner:

        if not remaining_members:

            sessions_response = sessions_table.query(
                IndexName="group-session-index",
                KeyConditionExpression=Key("group_id").eq(group_id)
            )

            for gaming_session in sessions_response.get("Items", []):
                session_id = gaming_session["session_id"]

                session_members_response = session_members_table.query(
                    KeyConditionExpression=Key("session_id").eq(session_id)
                )

                for session_member in session_members_response.get("Items", []):
                    session_members_table.delete_item(
                        Key={
                            "session_id": session_id,
                            "user_id": session_member["user_id"]
                        }
                    )

                sessions_table.delete_item(
                    Key={
                        "session_id": session_id
                    }
                )

            members_table.delete_item(
                Key={
                    "group_id": group_id,
                    "user_id": user_id
                }
            )

            groups_table.delete_item(
                Key={
                    "group_id": group_id
                }
            )

            flash("You left the group. The group was deleted because it had no remaining members.")

            return redirect(url_for("groups"))

        remaining_members.sort(
            key=lambda member: member.get("joined_at", "")
        )

        new_owner = remaining_members[0]
        new_owner_id = new_owner["user_id"]

        members_table.update_item(
            Key={
                "group_id": group_id,
                "user_id": new_owner_id
            },
            UpdateExpression="SET #role = :role",
            ExpressionAttributeNames={
                "#role": "role"
            },
            ExpressionAttributeValues={
                ":role": "owner"
            }
        )

        groups_table.update_item(
            Key={
                "group_id": group_id
            },
            UpdateExpression="SET owner_id = :owner_id",
            ExpressionAttributeValues={
                ":owner_id": new_owner_id
            }
        )

        members_table.delete_item(
            Key={
                "group_id": group_id,
                "user_id": user_id
            }
        )

        flash("You left the group. Ownership was automatically transferred to another member.")

        return redirect(url_for("groups"))

    members_table.delete_item(
        Key={
            "group_id": group_id,
            "user_id": user_id
        }
    )

    flash("You have left the group.")

    return redirect(url_for("groups"))

@app.route('/group/<group_id>/edit', methods=['GET', 'POST'])
def edit_group(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    groups_table = get_table(Config.GROUPS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)

    group = groups_table.get_item(Key={'group_id': group_id}).get('Item')
    if not group:
        flash('Group not found.')
        return redirect(url_for('groups'))

    if group.get('owner_id') != user_id:
        flash('Only the group owner can edit this group.')
        return redirect(url_for('group_details', group_id=group_id))

    games = games_table.scan().get('Items', [])
    games.sort(key=lambda game: game.get('game_name', '').lower())

    if request.method == 'POST':
        group_name = request.form.get('group_name', '').strip()
        game_id = request.form.get('game_id', '').strip()

        if not group_name or not game_id:
            flash('Group name and game are required.')
            return redirect(url_for('edit_group', group_id=group_id))

        game = games_table.get_item(Key={'game_id': game_id}).get('Item')
        if not game:
            flash('Game not found.')
            return redirect(url_for('edit_group', group_id=group_id))

        groups_table.update_item(
            Key={'group_id': group_id},
            UpdateExpression='SET group_name = :group_name, game_id = :game_id',
            ExpressionAttributeValues={
                ':group_name': group_name,
                ':game_id': game_id
            }
        )

        flash('Group updated successfully.')
        return redirect(url_for('group_details', group_id=group_id))

    return render_template('edit_group.html', group=group, games=games)

@app.route('/sessions')
def sessions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    sessions_table = get_table(Config.SESSIONS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    membership_response = members_table.query(IndexName='user-index', KeyConditionExpression=Key('user_id').eq(user_id))
    memberships = membership_response.get('Items', [])
    group_ids = [membership['group_id'] for membership in memberships]
    gaming_sessions = []
    for group_id in group_ids:
        response = sessions_table.query(IndexName='group-session-index', KeyConditionExpression=Key('group_id').eq(group_id))
        group_sessions = response.get('Items', [])
        for gaming_session in group_sessions:
            group_response = groups_table.get_item(Key={'group_id': group_id})
            group = group_response.get('Item')
            if group:
                gaming_session['group_name'] = group.get('group_name', 'Unknown Group')
            gaming_sessions.append(gaming_session)
    gaming_sessions.sort(key=lambda x: x.get('session_time', ''))
    return render_template('sessions.html', sessions=gaming_sessions)

@app.route('/create-session', methods=['GET', 'POST'])
def create_session():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)
    membership_response = members_table.query(IndexName='user-index', KeyConditionExpression=Key('user_id').eq(user_id))
    memberships = membership_response.get('Items', [])
    groups = []
    for membership in memberships:
        group_response = groups_table.get_item(Key={'group_id': membership['group_id']})
        group = group_response.get('Item')
        if group:
            groups.append(group)
    selected_group_id = request.args.get('group_id')
    if request.method == 'POST':
        group_id = request.form.get('group_id')
        session_name = request.form.get('session_name')
        session_time = request.form.get('session_time')
        description = request.form.get('description')
        valid_group = False
        for group in groups:
            if group['group_id'] == group_id:
                valid_group = True
                break
        if not valid_group:
            flash('You are not a member of this group.')
            return redirect(url_for('create_session'))
        session_id = str(uuid.uuid4())
        gaming_session = {'session_id': session_id, 'group_id': group_id, 'session_name': session_name, 'session_time': session_time, 'description': description, 'created_by': user_id, 'created_at': datetime.utcnow().isoformat()}
        sessions_table.put_item(Item=gaming_session)
        try:
            save_analytics_event(
                "session_created",
                user_id,
                {
                    "session_id": session_id,
                    "group_id": group_id,
                    "session_name": session_name
                }
            )
        except Exception as error:
            print(
                "Analytics event error:",
                str(error)
            )
        session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)
        session_members_table.put_item(Item={'session_id': session_id, 'user_id': user_id, 'joined_at': datetime.utcnow().isoformat()})
        flash('Gaming session created successfully!')
        return redirect(url_for('group_details', group_id=group_id))
    return render_template('create_session.html', groups=groups, selected_group_id=selected_group_id)

@app.route('/join-session/<session_id>', methods=['POST'])
def join_session(session_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    sessions_table = get_table(Config.SESSIONS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)
    session_response = sessions_table.get_item(Key={'session_id': session_id})
    gaming_session = session_response.get('Item')
    if not gaming_session:
        flash('Gaming session not found.')
        return redirect(url_for('sessions'))
    group_id = gaming_session['group_id']
    membership_response = members_table.get_item(Key={'group_id': group_id, 'user_id': user_id})
    membership = membership_response.get('Item')
    if not membership:
        flash('You must be a group member to join this session.')
        return redirect(url_for('sessions'))
    existing_response = session_members_table.get_item(Key={'session_id': session_id, 'user_id': user_id})
    if existing_response.get('Item'):
        flash('You have already joined this session.')
        return redirect(url_for('sessions'))
    session_members_table.put_item(Item={'session_id': session_id, 'user_id': user_id, 'joined_at': datetime.utcnow().isoformat()})
    flash('You joined the gaming session!')
    return redirect(url_for('sessions'))

@app.route('/session/<session_id>')
def session_details(session_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    sessions_table = get_table(Config.SESSIONS_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    session_response = sessions_table.get_item(Key={'session_id': session_id})
    gaming_session = session_response.get('Item')
    if not gaming_session:
        flash('Gaming session not found.')
        return redirect(url_for('sessions'))
    group_id = gaming_session['group_id']
    membership_response = members_table.get_item(Key={'group_id': group_id, 'user_id': user_id})
    membership = membership_response.get('Item')
    if not membership:
        flash('You are not a member of this group.')
        return redirect(url_for('sessions'))
    group_response = groups_table.get_item(Key={'group_id': group_id})
    group = group_response.get('Item')
    if not group:
        flash('Group not found.')
        return redirect(url_for('groups'))
    members_response = session_members_table.query(KeyConditionExpression=Key('session_id').eq(session_id))
    session_members = members_response.get('Items', [])
    members = []
    for session_member in session_members:
        member_user_id = session_member['user_id']
        user_response = users_table.get_item(Key={'user_id': member_user_id})
        member_user = user_response.get('Item')
        if member_user:
            members.append({'user_id': member_user_id, 'username': member_user.get('username', 'Unknown'), 'region': member_user.get('region', ''), 'joined_at': session_member.get('joined_at', '')})
    return render_template('session_details.html', gaming_session=gaming_session, group=group, members=members, current_user_id=user_id)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    invitations_table = get_table(Config.INVITATIONS_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    group_members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    response = users_table.get_item(Key={'user_id': user_id})
    current_user = response.get('Item')
    if not current_user or current_user.get('role') != 'admin':
        flash('You do not have permission to access the admin dashboard.')
        return redirect(url_for('dashboard'))
    users_count = users_table.scan(Select='COUNT').get('Count', 0)
    games_count = games_table.scan(Select='COUNT').get('Count', 0)
    groups_count = groups_table.scan(Select='COUNT').get('Count', 0)
    sessions_count = sessions_table.scan(Select='COUNT').get('Count', 0)
    player_games_count = player_games_table.scan(Select='COUNT').get('Count', 0)
    memberships_count = group_members_table.scan(Select='COUNT').get('Count', 0)
    invitations_response = invitations_table.scan()
    invitations = invitations_response.get('Items', [])
    pending_invitations_count = sum((1 for invitation in invitations if invitation.get('status') == 'pending'))
    accepted_invitations_count = sum((1 for invitation in invitations if invitation.get('status') == 'accepted'))
    rejected_invitations_count = sum((1 for invitation in invitations if invitation.get('status') == 'rejected'))
    return render_template('admin_dashboard.html', users_count=users_count, games_count=games_count, groups_count=groups_count, sessions_count=sessions_count, player_games_count=player_games_count, memberships_count=memberships_count, pending_invitations_count=pending_invitations_count, accepted_invitations_count=accepted_invitations_count, rejected_invitations_count=rejected_invitations_count)

@app.route("/admin/analytics")
def admin_analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))

    users_table = get_table(Config.USERS_TABLE)

    user_response = users_table.get_item(
        Key={"user_id": session["user_id"]}
    )

    current_user = user_response.get("Item")

    if not current_user or current_user.get("role") != "admin":
        flash("You do not have permission to access analytics.")
        return redirect(url_for("dashboard"))

    analytics_step_id = session.get("analytics_step_id")

    base = "analytics/results/summary"

    try:
        event_counts = read_json_folder(
            f"{base}/event_counts/"
        )

        game_search_counts = read_json_folder(
            f"{base}/game_search_counts/"
        )

        average_recommendations_data = read_json_folder(
            f"{base}/average_recommendations/"
        )

        active_users_data = read_json_folder(
            f"{base}/active_users/"
        )

        session_count_data = read_json_folder(
            f"{base}/session_count/"
        )

        invitation_count_data = read_json_folder(
            f"{base}/invitation_count/"
        )

    except Exception as error:
        print("Analytics read error:", str(error))

        flash("Unable to load analytics data.")

        return render_template(
            "admin_analytics.html",
            event_counts=[],
            game_search_counts=[],
            average_recommendations=0,
            active_users=0,
            sessions_created=0,
            invitations_sent=0,
            analytics_step_id=analytics_step_id
        )

    average_recommendations = 0

    if average_recommendations_data:
        average_recommendations = (
            average_recommendations_data[0]
            .get("average_recommendations", 0)
            or 0
        )

    active_users = len(active_users_data)

    sessions_created = 0

    if session_count_data:
        sessions_created = (
            session_count_data[0]
            .get("sessions_created", 0)
            or 0
        )

    invitations_sent = 0

    if invitation_count_data:
        invitations_sent = (
            invitation_count_data[0]
            .get("invitations_sent", 0)
            or 0
        )

    return render_template(
        "admin_analytics.html",
        event_counts=event_counts,
        game_search_counts=game_search_counts,
        average_recommendations=average_recommendations,
        active_users=active_users,
        sessions_created=sessions_created,
        invitations_sent=invitations_sent,
        analytics_step_id=analytics_step_id
    )

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    response = users_table.get_item(Key={'user_id': user_id})
    current_user = response.get('Item')
    if not current_user or current_user.get('role') != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('dashboard'))
    users_response = users_table.scan()
    users = users_response.get('Items', [])
    users.sort(key=lambda x: x.get('username', '').lower())
    return render_template('admin_users.html', users=users, current_user_id=user_id)

@app.route('/admin/users/delete/<target_user_id>', methods=['POST'])
def delete_user(target_user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    group_members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    invitations_table = get_table(Config.INVITATIONS_TABLE)
    session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)
    admin_response = users_table.get_item(Key={'user_id': admin_id})
    admin = admin_response.get('Item')
    if not admin or admin.get('role') != 'admin':
        flash('You do not have permission to perform this action.')
        return redirect(url_for('dashboard'))
    if target_user_id == admin_id:
        flash('You cannot delete your own admin account.')
        return redirect(url_for('admin_users'))
    target_response = users_table.get_item(Key={'user_id': target_user_id})
    target_user = target_response.get('Item')
    if not target_user:
        flash('User not found.')
        return redirect(url_for('admin_users'))
    player_games_response = player_games_table.query(KeyConditionExpression=Key('user_id').eq(target_user_id))
    for player_game in player_games_response.get('Items', []):
        player_games_table.delete_item(Key={'user_id': target_user_id, 'game_id': player_game['game_id']})
    memberships_response = group_members_table.query(IndexName='user-index', KeyConditionExpression=Key('user_id').eq(target_user_id))
    for membership in memberships_response.get('Items', []):
        group_members_table.delete_item(Key={'group_id': membership['group_id'], 'user_id': target_user_id})
    invitations_response = invitations_table.query(KeyConditionExpression=Key('receiver_id').eq(target_user_id))
    for invitation in invitations_response.get('Items', []):
        invitations_table.delete_item(Key={'receiver_id': target_user_id, 'invitation_id': invitation['invitation_id']})
    sent_invitations_response = invitations_table.scan(FilterExpression=Attr('sender_id').eq(target_user_id))
    for invitation in sent_invitations_response.get('Items', []):
        invitations_table.delete_item(Key={'receiver_id': invitation['receiver_id'], 'invitation_id': invitation['invitation_id']})
    session_members_response = session_members_table.scan(FilterExpression=Attr('user_id').eq(target_user_id))
    for session_member in session_members_response.get('Items', []):
        session_members_table.delete_item(Key={'session_id': session_member['session_id'], 'user_id': target_user_id})
    users_table.delete_item(Key={'user_id': target_user_id})
    flash(f"User {target_user.get('username', '')} and related records were deleted.")
    return redirect(url_for('admin_users'))

@app.route('/admin/games')
def admin_games():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    response = users_table.get_item(Key={'user_id': user_id})
    current_user = response.get('Item')
    if not current_user or current_user.get('role') != 'admin':
        flash('You do not have permission to access this page.')
        return redirect(url_for('dashboard'))
    games_response = games_table.scan()
    games = games_response.get('Items', [])
    games.sort(key=lambda x: x.get('game_name', '').lower())
    return render_template('admin_games.html', games=games)

@app.route('/admin/games/add', methods=['POST'])
def add_admin_game():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    response = users_table.get_item(Key={'user_id': user_id})
    current_user = response.get('Item')
    if not current_user or current_user.get('role') != 'admin':
        flash('You do not have permission to perform this action.')
        return redirect(url_for('dashboard'))
    game_name = request.form.get('game_name', '').strip()
    genre = request.form.get('genre', '').strip()
    if not game_name or not genre:
        flash('Game name and genre are required.')
        return redirect(url_for('admin_games'))
    existing_response = games_table.scan()
    existing_games = existing_response.get('Items', [])
    for game in existing_games:
        if game.get('game_name', '').lower() == game_name.lower():
            flash('This game is already exists.')
            return redirect(url_for('admin_games'))
    game_id = str(uuid.uuid4())
    games_table.put_item(Item={'game_id': game_id, 'game_name': game_name, 'genre': genre})
    flash(f'{game_name} was added successfully.')
    return redirect(url_for('admin_games'))

@app.route('/admin/games/delete/<game_id>', methods=['POST'])
def delete_admin_game(game_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    admin_id = session['user_id']
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    player_games_table = get_table(Config.PLAYER_GAMES_TABLE)
    response = users_table.get_item(Key={'user_id': admin_id})
    current_user = response.get('Item')
    if not current_user or current_user.get('role') != 'admin':
        flash('You do not have permission to perform this action.')
        return redirect(url_for('dashboard'))
    game_response = games_table.get_item(Key={'game_id': game_id})
    game = game_response.get('Item')
    if not game:
        flash('Game not found.')
        return redirect(url_for('admin_games'))
    player_games_response = player_games_table.query(IndexName='game-index', KeyConditionExpression=Key('game_id').eq(game_id))
    player_games = player_games_response.get('Items', [])
    if player_games:
        flash(f"Cannot delete {game.get('game_name', 'this game')} because {len(player_games)} player profile(s) are currently using it.")
        return redirect(url_for('admin_games'))
    games_table.delete_item(Key={'game_id': game_id})
    flash(f"{game.get('game_name', 'Game')} was deleted successfully.")
    return redirect(url_for('admin_games'))

@app.route('/api/lambda/users', methods=['GET'])
def lambda_get_users():
    try:
        users_table = get_table(Config.USERS_TABLE)
        result = users_table.scan(ProjectionExpression='user_id, username, #email, #region', ExpressionAttributeNames={'#email': 'email', '#region': 'region'})
        return (jsonify({'users': result.get('Items', [])}), 200)
    except Exception as error:
        print('Lambda API error:', str(error))
        return (jsonify({'message': 'Unable to retrieve users'}), 500)

@app.route('/group/<group_id>/add-member', methods=['POST'])
def add_group_member(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user_id = session['user_id']
    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    group_response = groups_table.get_item(Key={'group_id': group_id})
    group = group_response.get('Item')
    if not group:
        flash('Group not found.')
        return redirect(url_for('groups'))
    if group.get('owner_id') != current_user_id:
        flash('Only the group owner can add teammates.')
        return redirect(url_for('group_details', group_id=group_id))
    target_user_id = request.form.get('user_id')
    if not target_user_id:
        flash('Please select a player.')
        return redirect(url_for('group_details', group_id=group_id))
    if target_user_id == current_user_id:
        flash('You cannot add yourself to your own group.')
        return redirect(url_for('group_details', group_id=group_id))
    user_response = users_table.get_item(Key={'user_id': target_user_id})
    target_user = user_response.get('Item')
    if not target_user:
        flash('Player not found.')
        return redirect(url_for('group_details', group_id=group_id))
    existing_member = members_table.get_item(Key={'group_id': group_id, 'user_id': target_user_id})
    if existing_member.get('Item'):
        flash(f"{target_user.get('username')} is already in the group.")
        return redirect(url_for('group_details', group_id=group_id))
    members_table.put_item(Item={'group_id': group_id, 'user_id': target_user_id, 'username': target_user.get('username'), 'joined_at': datetime.utcnow().isoformat()})
    flash(f"{target_user.get('username')} has been added to the group.")
    return redirect(url_for('group_details', group_id=group_id))

@app.route('/group/<group_id>/search-players')
def search_group_players(group_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    current_user_id = session['user_id']
    groups_table = get_table(Config.GROUPS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    group_response = groups_table.get_item(Key={'group_id': group_id})
    group = group_response.get('Item')
    if not group:
        flash('Group not found.')
        return redirect(url_for('groups'))
    if group.get('owner_id') != current_user_id:
        flash('Only the group owner can add teammates.')
        return redirect(url_for('group_details', group_id=group_id))
    search = request.args.get('search', '').strip()
    players = []
    if search:
        response = users_table.query(IndexName='username-index', KeyConditionExpression='username = :username', ExpressionAttributeValues={':username': search})
        players = response.get('Items', [])
    return render_template('search_group_players.html', group=group, players=players, search=search)

@app.route('/api/lambda/users', methods=['POST'])
def lambda_create_user():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        region = data.get('region', '')
        if not username or not email:
            return (jsonify({'message': 'username and email are required'}), 400)
        users_table = get_table(Config.USERS_TABLE)
        user_id = str(uuid.uuid4())
        user = {'user_id': user_id, 'username': username, 'email': email, 'region': region, 'role': 'player'}
        users_table.put_item(Item=user)
        return (jsonify({'message': 'User created successfully', 'user': user}), 201)
    except Exception as error:
        print('Lambda create user error:', str(error))
        return (jsonify({'message': 'Unable to create user'}), 500)

@app.route('/create-group', methods=['GET', 'POST'])
def create_group():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    users_table = get_table(Config.USERS_TABLE)
    games_table = get_table(Config.GAMES_TABLE)
    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    user_id = session['user_id']
    user_response = users_table.get_item(Key={'user_id': user_id})
    user = user_response.get('Item')
    if not user:
        session.clear()
        return redirect(url_for('login'))
    games_response = games_table.scan()
    games = games_response.get('Items', [])
    if request.method == 'GET':
        return render_template('create_group.html', games=games)
    group_name = request.form.get('group_name', '').strip()
    game_id = request.form.get('game_id', '').strip()
    if not group_name:
        flash('Please enter a group name.')
        return redirect(url_for('create_group'))
    if not game_id:
        flash('Please select a game.')
        return redirect(url_for('create_group'))
    game_response = games_table.get_item(Key={'game_id': game_id})
    game = game_response.get('Item')
    if not game:
        flash('Selected game was not found.')
        return redirect(url_for('create_group'))
    group_id = str(uuid.uuid4())
    group = {'group_id': group_id, 'owner_id': user_id, 'game_id': game_id, 'group_name': group_name, 'created_at': datetime.now(timezone.utc).isoformat()}
    groups_table.put_item(Item=group)
    members_table.put_item(Item={'group_id': group_id, 'user_id': user_id, 'username': user.get('username', session.get('username', '')), 'role': 'owner', 'joined_at': datetime.now(timezone.utc).isoformat()})
    flash(f"Group '{group_name}' created successfully.")
    return redirect(url_for('group_details', group_id=group_id))

@app.route("/group/<group_id>/remove-member/<target_user_id>", methods=["POST"])
def remove_group_member(group_id, target_user_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_user_id = session["user_id"]

    groups_table = get_table(Config.GROUPS_TABLE)
    members_table = get_table(Config.GROUP_MEMBERS_TABLE)
    users_table = get_table(Config.USERS_TABLE)
    session_members_table = get_table(Config.SESSION_MEMBERS_TABLE)
    sessions_table = get_table(Config.SESSIONS_TABLE)

    group = groups_table.get_item(
        Key={"group_id": group_id}
    ).get("Item")

    if not group:
        flash("Group not found.")
        return redirect(url_for("groups"))

    if group.get("owner_id") != current_user_id:
        flash("Only the group owner can remove members.")
        return redirect(
            url_for(
                "group_details",
                group_id=group_id
            )
        )

    if target_user_id == current_user_id:
        flash("You cannot remove yourself. Use Leave Group instead.")
        return redirect(
            url_for(
                "group_details",
                group_id=group_id
            )
        )

    target_membership = members_table.get_item(
        Key={
            "group_id": group_id,
            "user_id": target_user_id
        }
    ).get("Item")

    if not target_membership:
        flash("This player is not a member of the group.")
        return redirect(
            url_for(
                "group_details",
                group_id=group_id
            )
        )

    target_user = users_table.get_item(
        Key={"user_id": target_user_id}
    ).get("Item")

    username = (
        target_user.get("username", "Player")
        if target_user
        else "Player"
    )

    sessions_response = sessions_table.query(
        IndexName="group-session-index",
        KeyConditionExpression=Key("group_id").eq(group_id)
    )

    for gaming_session in sessions_response.get("Items", []):
        session_id = gaming_session["session_id"]

        existing_session_member = session_members_table.get_item(
            Key={
                "session_id": session_id,
                "user_id": target_user_id
            }
        ).get("Item")

        if existing_session_member:
            session_members_table.delete_item(
                Key={
                    "session_id": session_id,
                    "user_id": target_user_id
                }
            )

    members_table.delete_item(
        Key={
            "group_id": group_id,
            "user_id": target_user_id
        }
    )

    flash(
        f"{username} was removed from the group successfully."
    )

    return redirect(
        url_for(
            "group_details",
            group_id=group_id
        )
    )

@app.route('/admin/analytics/run', methods=['POST'])
def run_admin_analytics():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    users_table = get_table(Config.USERS_TABLE)

    user_response = users_table.get_item(
        Key={'user_id': session['user_id']}
    )

    user = user_response.get('Item')

    if not user or user.get('role') != 'admin':
        flash('Admin access required.')
        return redirect(url_for('dashboard'))

    try:
        api_response = requests.post(
            Config.ANALYTICS_API_URL,
            timeout=15
        )

        data = api_response.json()

        if api_response.status_code in [200, 202] and data.get('success'):
            step_id = data.get('step_id', '')

            session['analytics_step_id'] = step_id

            flash(
                f'Analytics update started successfully. '
                f'EMR Step: {step_id}'
            )

        else:
            print(
                'Analytics API error:',
                api_response.status_code,
                api_response.text
            )

            flash('Unable to start analytics update.')

    except Exception as error:
        print(
            'Analytics trigger error:',
            str(error)
        )

        flash('Unable to start analytics update.')

    return redirect(
        url_for('admin_analytics')
    )

@app.route('/admin/analytics/status')
def admin_analytics_status():
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Not logged in.'
        }), 401

    users_table = get_table(Config.USERS_TABLE)

    user_response = users_table.get_item(
        Key={'user_id': session['user_id']}
    )

    user = user_response.get('Item')

    if not user or user.get('role') != 'admin':
        return jsonify({
            'success': False,
            'message': 'Admin access required.'
        }), 403

    step_id = session.get('analytics_step_id')

    if not step_id:
        return jsonify({
            'success': False,
            'message': 'No analytics job is currently being tracked.'
        }), 404

    try:
        base_url = Config.ANALYTICS_API_URL.rsplit(
            '/analytics/run',
            1
        )[0]

        status_url = (
            f'{base_url}/analytics/status/{step_id}'
        )

        api_response = requests.get(
            status_url,
            timeout=15
        )

        data = api_response.json()

        if not api_response.ok or not data.get('success'):
            return jsonify({
                'success': False,
                'message': data.get(
                    'message',
                    'Unable to check analytics status.'
                )
            }), api_response.status_code

        analytics = data.get('analytics', {})

        state = analytics.get(
            'state',
            'UNKNOWN'
        )

        message = analytics.get(
            'message',
            ''
        )

        if state in [
            'COMPLETED',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        ]:
            session.pop(
                'analytics_step_id',
                None
            )

        return jsonify({
            'success': True,
            'step_id': step_id,
            'state': state,
            'message': message
        })

    except Exception as error:
        print(
            'Analytics status error:',
            str(error)
        )

        return jsonify({
            'success': False,
            'message': 'Unable to check analytics status.'
        }), 500

@app.route('/game-deals')
def game_deals():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('game_deals.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)