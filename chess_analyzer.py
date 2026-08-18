import io
import requests
import chess
import chess.engine
import chess.pgn

# 1. Fetch Chess.com Games across multiple monthly archives
def fetch_chess_com_games(username, count=20):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    archives_url = f"https://api.chess.com/pub/player/{username.lower()}/games/archives"
    resp = requests.get(archives_url, headers=headers)
    if resp.status_code != 200:
        return []
    
    archives = resp.json().get("archives", [])
    if not archives:
        return []
    
    pgn_games = []
    # Crawl backward through recent monthly archives until reaching desired count
    for archive_url in reversed(archives):
        games_resp = requests.get(archive_url, headers=headers)
        if games_resp.status_code != 200:
            continue
        games_data = games_resp.json().get("games", [])
        for g in reversed(games_data):
            if "pgn" in g:
                game = chess.pgn.read_game(io.StringIO(g["pgn"]))
                if game:
                    pgn_games.append(game)
            if len(pgn_games) >= count:
                break
        if len(pgn_games) >= count:
            break
            
    return pgn_games[:count]

# 2. Fetch Lichess Games
def fetch_lichess_games(username, count=20):
    url = f"https://lichess.org/api/games/user/{username}?max={count}&evals=false"
    headers = {"Accept": "application/x-chess-pgn"}
    resp = requests.get(url, headers=headers)
    
    pgn_games = []
    pgn_io = io.StringIO(resp.text)
    while len(pgn_games) < count:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        pgn_games.append(game)
    return pgn_games

# 3. Analyze Games (Stockfish Engine Loop)
import chess
import chess.engine

def get_normalized_score(pov_score):
    """Converts a PovScore into a standard centipawn integer, handling forced mates."""
    if pov_score.is_mate():
        mate_moves = pov_score.mate()
        # Cap mate scores at 10,000 CPL to prevent math errors, decreasing slightly for longer mates
        return 10000 - abs(mate_moves) if mate_moves > 0 else -10000 + abs(mate_moves)
    
    # Cap standard evaluations at +/- 1000 (10 pawns) to prevent massive CPL skew
    score = pov_score.score()
    if score > 1000: return 1000
    if score < -1000: return -1000
    return score

def classify_move(prev_eval, current_eval, is_white):
    """Accurately classifies move quality based on Lichess-style thresholds and safeguards."""
    # Orient the evaluation so positive always means good for the player who just moved
    if not is_white:
        prev_eval = -prev_eval
        current_eval = -current_eval
        
    cpl_drop = prev_eval - current_eval
    
    # SAFEGUARD: If the player is already completely winning (+4.0) and remains winning (+2.0)
    # Ignore massive CPL drops so we don't flag safe consolidation moves as blunders.
    if prev_eval > 400 and current_eval > 200:
        if cpl_drop > 400: 
            return "Mistake", cpl_drop
        return "Good", max(0, int(cpl_drop))

    # SAFEGUARD: If the position is totally lost (-5.0) and they make a move that keeps it lost (-6.0)
    # Don't pile on fake blunders when there were no good moves available anyway.
    if prev_eval < -500 and current_eval < -500:
        return "Good", 0 

    # Standard Lichess Thresholds
    if cpl_drop >= 300: return "Blunder", int(cpl_drop)
    if cpl_drop >= 150: return "Mistake", int(cpl_drop)
    if cpl_drop >= 50:  return "Inaccuracy", int(cpl_drop)
    if cpl_drop <= 15:  return "Best", max(0, int(cpl_drop))
    
    return "Good", max(0, int(cpl_drop))

def analyze_games_local(games, username, engine_path, depth=15):
    """
    Analyzes games with advanced CPL tracking and move classification.
    """
    total_cpl = 0
    total_moves_analyzed = 0
    blunders_missed = 0
    blunders_allowed = 0
    move_qualities = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
    blunder_details = []
    
    with chess.engine.SimpleEngine.popen_uci(engine_path) as engine:
        # Tweak engine settings for faster bulk analysis without losing accuracy
        engine.configure({"Threads": 2, "Hash": 64})
        
        for game_idx, game in enumerate(games):
            board = game.board()
            
            # Determine which side the target user played
            white_player = game.headers.get("White", "").lower()
            user_is_white = username.lower() in white_player
            
            prev_eval = 20  # Standard opening starting eval
            
            for move_num, move in enumerate(game.mainline_moves()):
                is_users_turn = (board.turn == chess.WHITE) == user_is_white
                
                # Evaluate position BEFORE the move to find the best alternative
                info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
                best_move = info_before.get("pv", [None])[0]
                
                # Push the actual move played
                board.push(move)
                
                # Evaluate position AFTER the move
                info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
                current_eval = get_normalized_score(info_after["score"].white())
                
                if is_users_turn:
                    # Classify the player's move
                    quality, cpl_drop = classify_move(prev_eval, current_eval, user_is_white)
                    move_qualities[quality] += 1
                    
                    if quality != "Best":
                        total_cpl += cpl_drop
                    total_moves_analyzed += 1
                    
                    if quality == "Blunder":
                        phase = "opening" if move_num < 20 else "middlegame" if move_num < 60 else "endgame"
                        blunder_details.append({
                            "game_num": game_idx + 1,
                            "fen": board.fen(),
                            "user_move": move.uci(),
                            "best_move": best_move.uci() if best_move else "N/A",
                            "drop": cpl_drop,
                            "phase": phase,
                            "type": "Tactical/Material",
                            "move_num": move_num // 2 + 1,
                            "user_color": "white" if user_is_white else "black"
                        })
                else:
                    # Track if the opponent blundered (to see if the user missed it next turn)
                    opp_quality, opp_cpl_drop = classify_move(prev_eval, current_eval, not user_is_white)
                    if opp_quality == "Blunder":
                        blunders_allowed += 1

                prev_eval = current_eval
                
    acpl = round(total_cpl / max(1, total_moves_analyzed), 1)

    return {
        "username": username,
        "total_games": len(games),
        "acpl": acpl,
        "total_blunders": move_qualities["Blunder"],
        "blunders_missed": blunders_allowed - move_qualities["Blunder"], # Approximate missed tactics
        "blunders_allowed": blunders_allowed,
        "move_qualities": move_qualities,
        "blunder_details": blunder_details,
        # Rating DNA is mocked here; you can implement custom logic based on phase/quality data
        "rating_dna": {"Opening Precision": 75, "Tactical Vision": 65, "Endgame Technique": 80, "Threat Awareness": 70, "Consistency": 72}
    }
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    
    total_blunders = 0
    total_cpl = 0
    total_user_moves = 0
    blunders_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    blunders_allowed = 0
    blunders_missed = 0
    blunder_details = []
    game_history_stats = []

    for game_idx, game in enumerate(games):
        board = game.board()
        headers = game.headers
        user_is_white = headers.get("White", "").lower() == username.lower()
        user_color = chess.WHITE if user_is_white else chess.BLACK
        
        moves = list(game.mainline_moves())
        game_cpl = 0
        game_moves = 0
        peak_eval = 0

        for move_idx, move in enumerate(moves):
            is_user_turn = (board.turn == user_color)
            phase = "opening" if move_idx < 20 else ("middlegame" if move_idx < 60 else "endgame")

            if is_user_turn:
                info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
                best_move = info_before.get("pv", [None])[0]
                eval_before = info_before["score"].pov(user_color).score(mate_score=10000)
                fen_before = board.fen()

                if eval_before > peak_eval:
                    peak_eval = eval_before

                board.push(move)

                info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after = info_after["score"].pov(user_color).score(mate_score=10000)

                drop = eval_before - eval_after
                if drop > 0:
                    game_cpl += drop
                    total_cpl += drop
                game_moves += 1
                total_user_moves += 1

                # Blunder Detection & Classification
                if drop >= 200:
                    total_blunders += 1
                    blunders_by_phase[phase] += 1

                    if peak_eval >= 300 and eval_after <= 50:
                        error_type = "Conversion Slip (Lost Winning Position)"
                    elif eval_before >= 150 and eval_after <= 50:
                        error_type = "Missed Win / Missed Tactic"
                        blunders_missed += 1
                    else:
                        error_type = "Allowed Threat / Hung Piece"
                        blunders_allowed += 1

                    blunder_details.append({
                        "game_num": game_idx + 1,
                        "fen": fen_before,
                        "user_move": move.uci(),
                        "best_move": best_move.uci() if best_move else "N/A",
                        "drop": drop,
                        "phase": phase,
                        "type": error_type,
                        "move_num": (move_idx // 2) + 1,
                        "user_color": "white" if user_is_white else "black"
                    })
            else:
                board.push(move)

        game_acpl = round(game_cpl / max(1, game_moves), 1)
        game_history_stats.append({"game": game_idx + 1, "acpl": game_acpl})

    engine.quit()

    return {
        "username": username,
        "total_games": len(games),
        "total_blunders": total_blunders,
        "total_cpl": total_cpl,
        "total_user_moves": total_user_moves,
        "blunders_by_phase": blunders_by_phase,
        "blunders_allowed": blunders_allowed,
        "blunders_missed": blunders_missed,
        "acpl": round(total_cpl / max(1, total_user_moves), 1),
        "blunder_details": blunder_details,
        "game_history": game_history_stats
    }

# 4. Elo Calculator Helper
def calculate_elo_change(user_rating, opp_rating, result, k_factor=32):
    expected_score = 1 / (1 + 10 ** ((opp_rating - user_rating) / 400))
    rating_change = round(k_factor * (result - expected_score))
    return user_rating + rating_change, rating_change

# 5. Generate LLM Report
def generate_llm_report(report_data, provider="Ollama (Local)", api_key=""):
    prompt = f"""
    You are an expert chess coach. Analyze these metrics for player '{report_data['username']}':
    - Games Analyzed: {report_data['total_games']}
    - Overall ACPL: {report_data['acpl']}
    - Total Blunders: {report_data['total_blunders']}
    - Blunders by Phase: {report_data['blunders_by_phase']}
    - Allowed Threats: {report_data['blunders_allowed']}
    - Missed Opportunities: {report_data['blunders_missed']}

    Provide 2 specific weaknesses and 3 actionable training steps tailored to an Elo ~1000-1200 player.
    """
    
    if provider == "Ollama (Local)":
        url = "http://localhost:11434/api/generate"
        payload = {"model": "llama3.2", "prompt": prompt, "stream": False}
        try:
            res = requests.post(url, json=payload)
            return res.json().get("response", "No response generated.") if res.status_code == 200 else f"Error: {res.status_code}"
        except Exception as e:
            return f"Failed to connect to Ollama: {e}"
    return "Cloud API integration ready."
import io
import requests
import chess
import chess.engine
import chess.pgn

def fetch_chess_com_games(username, count=20):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    archives_url = f"https://api.chess.com/pub/player/{username.lower()}/games/archives"
    resp = requests.get(archives_url, headers=headers)
    if resp.status_code != 200:
        return []
    
    archives = resp.json().get("archives", [])
    if not archives:
        return []
    
    pgn_games = []
    for archive_url in reversed(archives):
        games_resp = requests.get(archive_url, headers=headers)
        if games_resp.status_code != 200:
            continue
        games_data = games_resp.json().get("games", [])
        for g in reversed(games_data):
            if "pgn" in g:
                game = chess.pgn.read_game(io.StringIO(g["pgn"]))
                if game:
                    pgn_games.append(game)
            if len(pgn_games) >= count:
                break
        if len(pgn_games) >= count:
            break
            
    return pgn_games[:count]

def fetch_lichess_games(username, count=20):
    url = f"https://lichess.org/api/games/user/{username}?max={count}&evals=false"
    headers = {"Accept": "application/x-chess-pgn"}
    resp = requests.get(url, headers=headers)
    
    pgn_games = []
    pgn_io = io.StringIO(resp.text)
    while len(pgn_games) < count:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        pgn_games.append(game)
    return pgn_games

def analyze_games_local(games, username, stockfish_path, depth=10):
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    
    total_blunders = 0
    total_cpl = 0
    total_user_moves = 0
    blunders_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    move_qualities = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
    blunders_allowed = 0
    blunders_missed = 0
    blunder_details = []
    game_history_stats = []

    for game_idx, game in enumerate(games):
        board = game.board()
        headers = game.headers
        user_is_white = headers.get("White", "").lower() == username.lower()
        user_color = chess.WHITE if user_is_white else chess.BLACK
        
        moves = list(game.mainline_moves())
        game_cpl = 0
        game_moves = 0

        for move_idx, move in enumerate(moves):
            is_user_turn = (board.turn == user_color)
            phase = "opening" if move_idx < 20 else ("middlegame" if move_idx < 60 else "endgame")

            if is_user_turn:
                info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
                best_move = info_before.get("pv", [None])[0]
                eval_before = info_before["score"].pov(user_color).score(mate_score=10000)
                fen_before = board.fen()

                board.push(move)

                info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after = info_after["score"].pov(user_color).score(mate_score=10000)

                drop = max(0, eval_before - eval_after)
                game_cpl += drop
                total_cpl += drop
                game_moves += 1
                total_user_moves += 1

                # Chessigma-style Move Quality Breakdown
                if drop <= 15:
                    move_qualities["Best"] += 1
                elif drop <= 45:
                    move_qualities["Good"] += 1
                elif drop <= 90:
                    move_qualities["Inaccuracy"] += 1
                elif drop < 200:
                    move_qualities["Mistake"] += 1
                else:
                    move_qualities["Blunder"] += 1
                    total_blunders += 1
                    blunders_by_phase[phase] += 1

                    error_type = "Missed Win / Tactic" if eval_before >= 150 else "Allowed Threat / Hung Piece"
                    if "Missed" in error_type:
                        blunders_missed += 1
                    else:
                        blunders_allowed += 1

                    blunder_details.append({
                        "game_num": game_idx + 1,
                        "fen": fen_before,
                        "user_move": move.uci(),
                        "best_move": best_move.uci() if best_move else "N/A",
                        "drop": drop,
                        "phase": phase,
                        "type": error_type,
                        "move_num": (move_idx // 2) + 1,
                        "user_color": "white" if user_is_white else "black"
                    })
            else:
                board.push(move)

        game_acpl = round(game_cpl / max(1, game_moves), 1)
        game_history_stats.append({"game": game_idx + 1, "acpl": game_acpl})

    engine.quit()

    return {
        "username": username,
        "total_games": len(games),
        "total_blunders": total_blunders,
        "total_cpl": total_cpl,
        "total_user_moves": total_user_moves,
        "blunders_by_phase": blunders_by_phase,
        "move_qualities": move_qualities,
        "blunders_allowed": blunders_allowed,
        "blunders_missed": blunders_missed,
        "acpl": round(total_cpl / max(1, total_user_moves), 1),
        "blunder_details": blunder_details,
        "game_history": game_history_stats
    }

def calculate_elo_change(user_rating, opp_rating, result, k_factor=32):
    expected_score = 1 / (1 + 10 ** ((opp_rating - user_rating) / 400))
    rating_change = round(k_factor * (result - expected_score))
    return user_rating + rating_change, rating_change

def generate_llm_report(report_data, provider="None (Disabled)", api_key="", custom_base_url=""):
    if provider == "None (Disabled)":
        return f"AI Coaching Disabled. Raw Metrics: ACPL {report_data['acpl']} across {report_data['total_games']} games with {report_data['total_blunders']} total blunders."

    prompt = f"""
    You are an expert chess coach. Analyze these metrics for player '{report_data['username']}':
    - Games Analyzed: {report_data['total_games']}
    - Overall ACPL: {report_data['acpl']}
    - Total Blunders: {report_data['total_blunders']}
    - Move Quality Breakdown: {report_data.get('move_qualities', {})}
    - Blunders by Phase: {report_data['blunders_by_phase']}

    Provide 2 specific weaknesses and 3 actionable training steps tailored to an Elo ~1000-1200 player.
    """

    try:
        if provider == "Ollama (Local)":
            url = custom_base_url or "http://localhost:11434/api/generate"
            res = requests.post(url, json={"model": "llama3.2", "prompt": prompt, "stream": False})
            return res.json().get("response", "No response.") if res.status_code == 200 else f"Error: {res.status_code}"

        elif provider == "OpenRouter":
            if not api_key: return "Please enter an OpenRouter API Key."
            headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "http://localhost:8501"}
            payload = {
                "model": "meta-llama/llama-3.2-3b-instruct:free",
                "messages": [{"role": "user", "content": prompt}]
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            return res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else f"OpenRouter Error: {res.text}"

        elif provider == "Omniroute":
            if not api_key: return "Please enter an Omniroute API Key."
            target_url = custom_base_url or "http://localhost:8000/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": "omniroute-default", "messages": [{"role": "user", "content": prompt}]}
            res = requests.post(target_url, headers=headers, json=payload)
            return res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else f"Omniroute Error: {res.text}"

        elif provider == "Gemini (Cloud)":
            import google.generativeai as genai
            if not api_key: return "Please enter a Gemini API Key."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            return model.generate_content(prompt).text

        elif provider == "OpenAI (Cloud)":
            from openai import OpenAI
            if not api_key: return "Please enter an OpenAI API Key."
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"Provider error: {str(e)}"

    return "Provider not configured."
import io
import re
import requests
import chess
import chess.engine
import chess.pgn

def fetch_chess_com_games(username, count=20):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    archives_url = f"https://api.chess.com/pub/player/{username.lower()}/games/archives"
    resp = requests.get(archives_url, headers=headers)
    if resp.status_code != 200:
        return []
    
    archives = resp.json().get("archives", [])
    if not archives:
        return []
    
    pgn_games = []
    for archive_url in reversed(archives):
        games_resp = requests.get(archive_url, headers=headers)
        if games_resp.status_code != 200:
            continue
        games_data = games_resp.json().get("games", [])
        for g in reversed(games_data):
            if "pgn" in g:
                game = chess.pgn.read_game(io.StringIO(g["pgn"]))
                if game:
                    pgn_games.append(game)
            if len(pgn_games) >= count:
                break
        if len(pgn_games) >= count:
            break
            
    return pgn_games[:count]

def fetch_lichess_games(username, count=20):
    url = f"https://lichess.org/api/games/user/{username}?max={count}&evals=false"
    headers = {"Accept": "application/x-chess-pgn"}
    resp = requests.get(url, headers=headers)
    
    pgn_games = []
    pgn_io = io.StringIO(resp.text)
    while len(pgn_games) < count:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        pgn_games.append(game)
    return pgn_games

def fetch_lichess_study_pgn(study_input):
    """Imports opening lines directly from a Lichess Study URL or Study ID."""
    study_id = study_input.split("/")[-1].split("#")[0].strip()
    url = f"https://lichess.org/study/{study_id}.pgn"
    resp = requests.get(url)
    if resp.status_code != 200:
        return []
    
    pgn_io = io.StringIO(resp.text)
    imported_chapters = []
    while True:
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            break
        chapter_title = game.headers.get("Event", "Lichess Chapter")
        eco = game.headers.get("ECO", "ECO")
        moves_uci = " ".join([m.uci() for m in game.mainline_moves()])
        imported_chapters.append((chapter_title, eco, moves_uci, f"Imported from Lichess Study: {study_id}"))
    
    return imported_chapters

def analyze_games_local(games, username, stockfish_path, depth=10):
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    
    total_blunders = 0
    total_cpl = 0
    total_user_moves = 0
    blunders_by_phase = {"opening": 0, "middlegame": 0, "endgame": 0}
    move_qualities = {"Best": 0, "Good": 0, "Inaccuracy": 0, "Mistake": 0, "Blunder": 0}
    blunders_allowed = 0
    blunders_missed = 0
    blunder_details = []
    game_history_stats = []

    for game_idx, game in enumerate(games):
        board = game.board()
        headers = game.headers
        user_is_white = headers.get("White", "").lower() == username.lower()
        user_color = chess.WHITE if user_is_white else chess.BLACK
        
        moves = list(game.mainline_moves())
        game_cpl = 0
        game_moves = 0

        for move_idx, move in enumerate(moves):
            is_user_turn = (board.turn == user_color)
            phase = "opening" if move_idx < 20 else ("middlegame" if move_idx < 60 else "endgame")

            if is_user_turn:
                info_before = engine.analyse(board, chess.engine.Limit(depth=depth))
                best_move = info_before.get("pv", [None])[0]
                eval_before = info_before["score"].pov(user_color).score(mate_score=10000)
                fen_before = board.fen()

                board.push(move)

                info_after = engine.analyse(board, chess.engine.Limit(depth=depth))
                eval_after = info_after["score"].pov(user_color).score(mate_score=10000)

                drop = max(0, eval_before - eval_after)
                game_cpl += drop
                total_cpl += drop
                game_moves += 1
                total_user_moves += 1

                if drop <= 15:
                    move_qualities["Best"] += 1
                elif drop <= 45:
                    move_qualities["Good"] += 1
                elif drop <= 90:
                    move_qualities["Inaccuracy"] += 1
                elif drop < 200:
                    move_qualities["Mistake"] += 1
                else:
                    move_qualities["Blunder"] += 1
                    total_blunders += 1
                    blunders_by_phase[phase] += 1

                    error_type = "Missed Win / Tactic" if eval_before >= 150 else "Allowed Threat / Hung Piece"
                    if "Missed" in error_type:
                        blunders_missed += 1
                    else:
                        blunders_allowed += 1

                    blunder_details.append({
                        "game_num": game_idx + 1,
                        "fen": fen_before,
                        "user_move": move.uci(),
                        "best_move": best_move.uci() if best_move else "N/A",
                        "drop": drop,
                        "phase": phase,
                        "type": error_type,
                        "move_num": (move_idx // 2) + 1,
                        "user_color": "white" if user_is_white else "black"
                    })
            else:
                board.push(move)

        game_acpl = round(game_cpl / max(1, game_moves), 1)
        game_history_stats.append({"game": game_idx + 1, "acpl": game_acpl})

    engine.quit()

    # Calculate Rating DNA spider metrics (0 to 100 scale)
    tot_moves = max(1, total_user_moves)
    rating_dna = {
        "Opening Precision": max(10, min(100, int(100 - (blunders_by_phase["opening"] * 20)))),
        "Tactical Vision": max(10, min(100, int(((move_qualities["Best"] + move_qualities["Good"]) / tot_moves) * 100))),
        "Endgame Technique": max(10, min(100, int(100 - (blunders_by_phase["endgame"] * 20)))),
        "Threat Awareness": max(10, min(100, int(100 - (blunders_allowed * 15)))),
        "Consistency": max(10, min(100, int(100 - (total_cpl / tot_moves))))
    }

    return {
        "username": username,
        "total_games": len(games),
        "total_blunders": total_blunders,
        "total_cpl": total_cpl,
        "total_user_moves": total_user_moves,
        "blunders_by_phase": blunders_by_phase,
        "move_qualities": move_qualities,
        "blunders_allowed": blunders_allowed,
        "blunders_missed": blunders_missed,
        "acpl": round(total_cpl / max(1, total_user_moves), 1),
        "rating_dna": rating_dna,
        "blunder_details": blunder_details,
        "game_history": game_history_stats
    }

def calculate_elo_change(user_rating, opp_rating, result, k_factor=32):
    expected_score = 1 / (1 + 10 ** ((opp_rating - user_rating) / 400))
    rating_change = round(k_factor * (result - expected_score))
    return user_rating + rating_change, rating_change

def ask_ai_coach(query, context_data, provider="None (Disabled)", api_key="", custom_base_url=""):
    if provider == "None (Disabled)":
        return "AI Coaching is disabled. Select an active provider in the sidebar."

    system_prompt = f"""
    You are an expert AI Chess Coach analyzing history for player '{context_data.get('username', 'Player')}'.
    Player Performance Data:
    - Games Analyzed: {context_data.get('total_games', 0)}
    - ACPL: {context_data.get('acpl', 0)}
    - Total Blunders: {context_data.get('total_blunders', 0)}
    - Blunders by Phase: {context_data.get('blunders_by_phase', {})}
    - Move Quality Stats: {context_data.get('move_qualities', {})}
    - Rating DNA: {context_data.get('rating_dna', {})}

    Answer the player's question directly, clearly, and concisely based on their actual game history.
    User Question: {query}
    """

    try:
        if provider == "Ollama (Local)":
            url = custom_base_url or "http://localhost:11434/api/generate"
            res = requests.post(url, json={"model": "llama3.2", "prompt": system_prompt, "stream": False})
            return res.json().get("response", "No response.") if res.status_code == 200 else f"Error: {res.status_code}"

        elif provider == "OpenRouter":
            if not api_key: return "Please enter an OpenRouter API Key."
            headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": "http://localhost:8501"}
            payload = {"model": "meta-llama/llama-3.2-3b-instruct:free", "messages": [{"role": "user", "content": system_prompt}]}
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            return res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else f"OpenRouter Error: {res.text}"

        elif provider == "Omniroute":
            if not api_key: return "Please enter an Omniroute API Key."
            target_url = custom_base_url or "http://localhost:8000/v1/chat/completions"
            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {"model": "omniroute-default", "messages": [{"role": "user", "content": system_prompt}]}
            res = requests.post(target_url, headers=headers, json=payload)
            return res.json()["choices"][0]["message"]["content"] if res.status_code == 200 else f"Omniroute Error: {res.text}"

        elif provider == "Gemini (Cloud)":
            import google.generativeai as genai
            if not api_key: return "Please enter a Gemini API Key."
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            return model.generate_content(system_prompt).text

        elif provider == "OpenAI (Cloud)":
            from openai import OpenAI
            if not api_key: return "Please enter an OpenAI API Key."
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": system_prompt}])
            return response.choices[0].message.content
    except Exception as e:
        return f"Provider error: {str(e)}"

    return "Provider not configured."

def generate_llm_report(report_data, provider="None (Disabled)", api_key="", custom_base_url=""):
    return ask_ai_coach("Give me my weekly coaching report breakdown, 2 core weaknesses, and 3 specific training steps.", report_data, provider, api_key, custom_base_url)