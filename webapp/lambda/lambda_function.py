import json
import os
import urllib.error
import urllib.parse
import urllib.request
import boto3

ECS_API_URL = os.environ.get("ECS_API_URL")
RIOT_API_KEY = os.environ.get("RIOT_API_KEY")

CHEAPSHARK_API_URL = "https://www.cheapshark.com/api/1.0"
RIOT_ACCOUNT_API_URL = "https://asia.api.riotgames.com"
RIOT_PLATFORM_API_URL = "https://vn2.api.riotgames.com"

EMR_CLUSTER_ID = os.environ.get("EMR_CLUSTER_ID")
ANALYTICS_SCRIPT_PATH = os.environ.get(
    "ANALYTICS_SCRIPT_PATH",
    "s3://gameconnect-s3994124-data/analytics/scripts/analytics_job.py"
)

emr = boto3.client("emr")

def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }

def read_json_response(api_response):
    raw = api_response.read()
    return json.loads(raw.decode("utf-8")) if raw else None

def http_get_json(url, headers=None, timeout=10):
    req = urllib.request.Request(
        url,
        headers=headers or {"Accept": "application/json"},
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=timeout) as api_response:
        return api_response.status, read_json_response(api_response)

def cheapshark_get(url):
    return http_get_json(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "GameConnect/1.0 RMIT Cloud Assessment"
        }
    )

def riot_get(url):
    if not RIOT_API_KEY:
        raise RuntimeError("RIOT_API_KEY is not configured")

    return http_get_json(
        url,
        headers={
            "Accept": "application/json",
            "X-Riot-Token": RIOT_API_KEY,
            "User-Agent": "GameConnect/1.0"
        }
    )

def get_method(event):
    method = event.get("httpMethod")
    if not method:
        method = event.get("requestContext", {}).get("http", {}).get("method", "GET")
    return method.upper()

def get_path(event):
    return event.get("rawPath") or event.get("path") or "/"

def error_body(error):
    try:
        return error.read().decode("utf-8", errors="replace")
    except Exception:
        return str(error)

def start_analytics_job():
    if not EMR_CLUSTER_ID:
        raise RuntimeError("EMR_CLUSTER_ID is not configured")

    if not ANALYTICS_SCRIPT_PATH:
        raise RuntimeError("ANALYTICS_SCRIPT_PATH is not configured")

    result = emr.add_job_flow_steps(
        JobFlowId=EMR_CLUSTER_ID,
        Steps=[
            {
                "Name": "GameConnect Analytics",
                "ActionOnFailure": "CONTINUE",
                "HadoopJarStep": {
                    "Jar": "command-runner.jar",
                    "Args": [
                        "spark-submit",
                        ANALYTICS_SCRIPT_PATH
                    ]
                }
            }
        ]
    )

    step_ids = result.get("StepIds") or []

    if not step_ids:
        raise RuntimeError("EMR did not return a step ID")

    return step_ids[0]

def get_analytics_step_status(step_id):
    if not EMR_CLUSTER_ID:
        raise RuntimeError("EMR_CLUSTER_ID is not configured")

    result = emr.describe_step(
        ClusterId=EMR_CLUSTER_ID,
        StepId=step_id
    )

    step = result.get("Step") or {}
    status = step.get("Status") or {}
    state_change_reason = status.get("StateChangeReason") or {}

    return {
        "step_id": step_id,
        "name": step.get("Name"),
        "state": status.get("State"),
        "message": state_change_reason.get("Message")
    }

def lambda_handler(event, context):
    method = get_method(event)
    path = get_path(event)

    print("METHOD:", method)
    print("PATH:", path)

    if method == "OPTIONS":
        return response(200, {"success": True, "message": "CORS OK"})

    if method == "POST" and path.rstrip("/") == "/analytics/run":
        try:
            step_id = start_analytics_job()

            return response(202, {
                "success": True,
                "message": "Analytics job started successfully",
                "cluster_id": EMR_CLUSTER_ID,
                "step_id": step_id,
                "script_path": ANALYTICS_SCRIPT_PATH
            })

        except Exception as error:
            print("EMR analytics start error:", str(error))

            return response(500, {
                "success": False,
                "message": "Unable to start analytics job",
                "error": str(error)
            })

    if method == "GET" and path.startswith("/analytics/status/"):
        parts = path.strip("/").split("/")

        if len(parts) != 3:
            return response(400, {
                "success": False,
                "message": "Use /analytics/status/{stepId}"
            })

        step_id = urllib.parse.unquote(parts[2]).strip()

        if not step_id:
            return response(400, {
                "success": False,
                "message": "stepId is required"
            })

        try:
            step_status = get_analytics_step_status(step_id)

            return response(200, {
                "success": True,
                "analytics": step_status
            })

        except Exception as error:
            print("EMR analytics status error:", str(error))

            return response(500, {
                "success": False,
                "message": "Unable to retrieve analytics job status",
                "error": str(error)
            })

    if method in ["GET", "POST"] and path.rstrip("/") == "/users":
        if not ECS_API_URL:
            return response(500, {
                "success": False,
                "message": "ECS_API_URL is not configured"
            })

        try:
            if method == "POST":
                try:
                    body = json.loads(event.get("body") or "{}")
                except json.JSONDecodeError:
                    return response(400, {
                        "success": False,
                        "message": "Request body must be valid JSON"
                    })

                req = urllib.request.Request(
                    ECS_API_URL,
                    data=json.dumps(body).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    method="POST"
                )
            else:
                req = urllib.request.Request(
                    ECS_API_URL,
                    headers={"Accept": "application/json"},
                    method="GET"
                )

            with urllib.request.urlopen(req, timeout=10) as ecs_response:
                raw = ecs_response.read()
                status_code = ecs_response.status
                try:
                    data = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    data = {"raw_response": raw.decode("utf-8", errors="replace")}

            return response(status_code, data)

        except urllib.error.HTTPError as error:
            return response(error.code, {
                "success": False,
                "message": "ECS API request failed",
                "error": error_body(error)
            })
        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to ECS API",
                "error": str(error)
            })

    if method == "GET" and path.startswith("/riot/account/"):
        parts = path.strip("/").split("/")

        if len(parts) != 4:
            return response(400, {
                "success": False,
                "message": "Use /riot/account/{gameName}/{tagLine}"
            })

        game_name = urllib.parse.unquote(parts[2]).strip()
        tag_line = urllib.parse.unquote(parts[3]).strip()

        if not game_name or not tag_line:
            return response(400, {
                "success": False,
                "message": "Riot game name and tag line are required"
            })

        if not RIOT_API_KEY:
            return response(500, {
                "success": False,
                "message": "RIOT_API_KEY is not configured"
            })

        try:
            encoded_name = urllib.parse.quote(game_name, safe="")
            encoded_tag = urllib.parse.quote(tag_line, safe="")

            account_url = (
                f"{RIOT_ACCOUNT_API_URL}/riot/account/v1/accounts/by-riot-id/"
                f"{encoded_name}/{encoded_tag}"
            )
            _, account = riot_get(account_url)

            puuid = (account or {}).get("puuid")
            if not puuid:
                return response(502, {
                    "success": False,
                    "message": "Riot account response did not contain a PUUID"
                })

            encoded_puuid = urllib.parse.quote(puuid, safe="")

            summoner_url = (
                f"{RIOT_PLATFORM_API_URL}/lol/summoner/v4/summoners/by-puuid/"
                f"{encoded_puuid}"
            )
            _, summoner = riot_get(summoner_url)

            league_url = (
                f"{RIOT_PLATFORM_API_URL}/lol/league/v4/entries/by-puuid/"
                f"{encoded_puuid}"
            )
            _, ranked_entries = riot_get(league_url)

            if not isinstance(ranked_entries, list):
                ranked_entries = []

            solo = next(
                (
                    entry for entry in ranked_entries
                    if entry.get("queueType") == "RANKED_SOLO_5x5"
                ),
                None
            )

            rank_text = "Unranked"
            if solo:
                tier = solo.get("tier", "")
                division = solo.get("rank", "")
                rank_text = f"{tier} {division}".strip() or "Unranked"

            return response(200, {
                "success": True,
                "game_name": (account or {}).get("gameName", game_name),
                "tag_line": (account or {}).get("tagLine", tag_line),
                "puuid": puuid,
                "rank": rank_text,
                "ranked_entries": ranked_entries,
                "account": account,
                "summoner": summoner
            })

        except urllib.error.HTTPError as error:
            if error.code == 401:
                message = "Riot API key is invalid."
            elif error.code == 403:
                message = "Riot API key expired or access is forbidden."
            elif error.code == 404:
                message = "Riot account was not found."
            elif error.code == 429:
                message = "Riot API rate limit reached."
            else:
                message = "Riot API request failed."

            return response(error.code, {
                "success": False,
                "message": message,
                "error": error_body(error)
            })

        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to Riot API",
                "error": str(error)
            })

    if method == "GET" and path.startswith("/cheapshark/games/"):
        parts = path.strip("/").split("/")

        if len(parts) != 3:
            return response(400, {
                "success": False,
                "message": "Use /cheapshark/games/{gameName}"
            })

        game_name = urllib.parse.unquote(parts[2]).strip()

        if not game_name:
            return response(400, {
                "success": False,
                "message": "gameName is required"
            })

        try:
            encoded_name = urllib.parse.quote(game_name, safe="")
            url = f"{CHEAPSHARK_API_URL}/games?title={encoded_name}"
            status_code, raw_games = cheapshark_get(url)

            games = []

            for game in raw_games or []:
                cheapest = game.get("cheapest")

                games.append({
                    "game_id": game.get("gameID"),
                    "steam_app_id": game.get("steamAppID"),
                    "name": game.get("external"),
                    "cheapest_price": cheapest,
                    "cheapest_deal_id": game.get("cheapestDealID"),
                    "thumb": game.get("thumb")
                })

            return response(status_code, {
                "success": True,
                "query": game_name,
                "count": len(games),
                "games": games
            })

        except urllib.error.HTTPError as error:
            return response(error.code, {
                "success": False,
                "message": "CheapShark API request failed",
                "error": error_body(error)
            })
        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to CheapShark API",
                "error": str(error)
            })

    if method == "GET" and (
        path.startswith("/cheapshark/deals/")
        or path.startswith("/cheapshark/game/")
    ):
        parts = path.strip("/").split("/")

        if len(parts) != 3:
            return response(400, {
                "success": False,
                "message": "Use /cheapshark/deals/{gameId}"
            })

        game_id = urllib.parse.unquote(parts[2]).strip()

        if not game_id.isdigit():
            return response(400, {
                "success": False,
                "message": "gameId must be a number"
            })

        try:
            url = f"{CHEAPSHARK_API_URL}/games?id={game_id}"
            status_code, raw_game = cheapshark_get(url)

            raw_game = raw_game or {}
            info = raw_game.get("info") or {}
            raw_deals = raw_game.get("deals") or []

            deals = []
            for deal in raw_deals:
                deals.append({
                    "deal_id": deal.get("dealID"),
                    "store_id": deal.get("storeID"),
                    "price": deal.get("price"),
                    "retail_price": deal.get("retailPrice"),
                    "savings": deal.get("savings")
                })

            return response(status_code, {
                "success": True,
                "game_id": game_id,
                "game": {
                    "title": info.get("title"),
                    "steam_app_id": info.get("steamAppID"),
                    "thumb": info.get("thumb")
                },
                "deals": deals
            })

        except urllib.error.HTTPError as error:
            return response(error.code, {
                "success": False,
                "message": "CheapShark API request failed",
                "error": error_body(error)
            })
        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to CheapShark API",
                "error": str(error)
            })

    if method == "GET" and path.rstrip("/") == "/cheapshark/deals":
        try:
            query = event.get("queryStringParameters") or {}

            allowed = [
                "storeID", "pageNumber", "pageSize", "sortBy", "desc",
                "lowerPrice", "upperPrice", "metacritic", "steamRating",
                "steamAppID", "publisher", "developer", "isOnSale",
                "savings", "aaa", "steamworks", "onSale", "reviewCount"
            ]

            query_parts = []
            for key in allowed:
                value = query.get(key)
                if value is not None:
                    query_parts.append(
                        f"{key}={urllib.parse.quote(str(value), safe='')}"
                    )

            url = f"{CHEAPSHARK_API_URL}/deals"
            if query_parts:
                url += "?" + "&".join(query_parts)

            status_code, data = cheapshark_get(url)

            return response(status_code, {
                "success": True,
                "deals": data
            })

        except urllib.error.HTTPError as error:
            return response(error.code, {
                "success": False,
                "message": "CheapShark API request failed",
                "error": error_body(error)
            })
        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to CheapShark API",
                "error": str(error)
            })

    if method == "GET" and path.rstrip("/") == "/deals":
        try:
            status_code, data = cheapshark_get(f"{CHEAPSHARK_API_URL}/deals")
            return response(status_code, {
                "success": True,
                "deals": data
            })
        except urllib.error.HTTPError as error:
            return response(error.code, {
                "success": False,
                "message": "CheapShark API request failed",
                "error": error_body(error)
            })
        except Exception as error:
            return response(502, {
                "success": False,
                "message": "Unable to connect to CheapShark API",
                "error": str(error)
            })

    return response(404, {
        "success": False,
        "message": "Route not found",
        "method": method,
        "path": path
    })
