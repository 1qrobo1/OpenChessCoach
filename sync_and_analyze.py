import time
import chess.pgn
import io
from db_manager import init_db, is_game_stored, save_game_analysis
from chess_analyzer import fetch_chess_com_games, fetch_lichess_games, analyze_games_local

def sync_user_games(username="1qschool1", platform="Chess.com", max_fetch=50):
    init_db()
    print(f"[{time.strftime('%H:%M:%S')}] Checking for new {platform} games for {username}...")
    
    games = fetch_chess_com_games(username, count=max_fetch) if platform == "Chess.com" else fetch_lichess_games(username, count=max_fetch)
    
    new_games = []
    for g in games:
        game_id = g.headers.get("Link", g.headers.get("UTCDate", "") + g.headers.get("UTCTime", ""))
        if not is_game_stored(game_id):
            new_games.append((game_id, g))
            
    print(f"Found {len(new_games)} unanalyzed games.")
    
    STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"
    for game_id, pgn_game in new_games:
        print(f"Analyzing game ID: {game_id}...")
        report = analyze_games_local([pgn_game], username, STOCKFISH_PATH, depth=10)
        
        pgn_str = str(pgn_game)
        save_game_analysis(
            game_id=game_id,
            platform=platform,
            username=username,
            acpl=report["acpl"],
            blunders=report["total_blunders"],
            missed=report["blunders_missed"],
            allowed=report["blunders_allowed"],
            pgn=pgn_str,
            blunder_details=report["blunder_details"]
        )
    print("Background sync complete!")

if __name__ == "__main__":
    sync_user_games()