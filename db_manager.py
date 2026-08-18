import sqlite3
import json

DB_PATH = "chess_coach.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Games Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            platform TEXT,
            username TEXT,
            date_played TEXT,
            acpl REAL,
            blunders INTEGER,
            missed_tactics INTEGER,
            allowed_threats INTEGER,
            pgn TEXT,
            analyzed INTEGER DEFAULT 0
        )
    ''')
    # Blunders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blunders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            fen TEXT,
            user_move TEXT,
            best_move TEXT,
            drop_cpl INTEGER,
            phase TEXT,
            error_type TEXT,
            move_num INTEGER,
            user_color TEXT,
            FOREIGN KEY (game_id) REFERENCES games (game_id)
        )
    ''')
    conn.commit()
    conn.close()

def is_game_stored(game_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_id FROM games WHERE game_id = ?", (game_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_game_analysis(game_id, platform, username, acpl, blunders, missed, allowed, pgn, blunder_details):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO games (game_id, platform, username, acpl, blunders, missed_tactics, allowed_threats, pgn, analyzed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (game_id, platform, username, acpl, blunders, missed, allowed, pgn))
    
    for b in blunder_details:
        cursor.execute('''
            INSERT INTO blunders (game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, b['fen'], b['user_move'], b['best_move'], b['drop'], b['phase'], b['type'], b['move_num'], b['user_color']))
    
    conn.commit()
    conn.close()

def load_all_stats(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT acpl, blunders, missed_tactics, allowed_threats FROM games WHERE username = ? AND analyzed = 1", (username,))
    games = cursor.fetchall()
    
    cursor.execute("SELECT game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color FROM blunders")
    blunders = cursor.fetchall()
    conn.close()
    return games, blunders
import sqlite3

DB_PATH = "chess_coach.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Games Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            platform TEXT,
            username TEXT,
            date_played TEXT,
            acpl REAL,
            blunders INTEGER,
            missed_tactics INTEGER,
            allowed_threats INTEGER,
            pgn TEXT,
            analyzed INTEGER DEFAULT 0
        )
    ''')
    
    # Blunders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blunders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            fen TEXT,
            user_move TEXT,
            best_move TEXT,
            drop_cpl INTEGER,
            phase TEXT,
            error_type TEXT,
            move_num INTEGER,
            user_color TEXT,
            FOREIGN KEY (game_id) REFERENCES games (game_id)
        )
    ''')

    # Repertoire Table (ChessReps style)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repertoire (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_name TEXT,
            eco_code TEXT,
            moves_uci TEXT,
            notes TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def is_game_stored(game_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_id FROM games WHERE game_id = ?", (game_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_game_analysis(game_id, platform, username, acpl, blunders, missed, allowed, pgn, blunder_details):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO games (game_id, platform, username, acpl, blunders, missed_tactics, allowed_threats, pgn, analyzed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (game_id, platform, username, acpl, blunders, missed, allowed, pgn))
    
    for b in blunder_details:
        cursor.execute('''
            INSERT INTO blunders (game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, b['fen'], b['user_move'], b['best_move'], b['drop'], b['phase'], b['type'], b['move_num'], b['user_color']))
    
    conn.commit()
    conn.close()

def load_all_stats(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT acpl, blunders, missed_tactics, allowed_threats FROM games WHERE username = ? AND analyzed = 1", (username,))
    games = cursor.fetchall()
    
    cursor.execute("SELECT game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color FROM blunders")
    blunders = cursor.fetchall()
    conn.close()
    return games, blunders

def add_repertoire_line(line_name, eco_code, moves_uci, notes=""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO repertoire (line_name, eco_code, moves_uci, notes) VALUES (?, ?, ?, ?)",
                   (line_name, eco_code, moves_uci, notes))
    conn.commit()
    conn.close()

def get_repertoire_lines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, line_name, eco_code, moves_uci, notes FROM repertoire")
    lines = cursor.fetchall()
    conn.close()
    return lines
import sqlite3
import datetime

DB_PATH = "chess_coach.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Games Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            platform TEXT,
            username TEXT,
            date_played TEXT,
            acpl REAL,
            blunders INTEGER,
            missed_tactics INTEGER,
            allowed_threats INTEGER,
            pgn TEXT,
            analyzed INTEGER DEFAULT 0
        )
    ''')
    
    # Blunders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS blunders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT,
            fen TEXT,
            user_move TEXT,
            best_move TEXT,
            drop_cpl INTEGER,
            phase TEXT,
            error_type TEXT,
            move_num INTEGER,
            user_color TEXT,
            FOREIGN KEY (game_id) REFERENCES games (game_id)
        )
    ''')

    # Repertoire Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS repertoire (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            line_name TEXT,
            eco_code TEXT,
            moves_uci TEXT,
            notes TEXT,
            category TEXT DEFAULT 'Opening'
        )
    ''')
    
    conn.commit()
    conn.close()
    seed_default_openings()

def seed_default_openings():
    """Auto-populates standard openings and famous traps so users do not have to create them manually."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM repertoire")
    if cursor.fetchone()[0] == 0:
        default_lines = [
            ("Italian Game: Fried Liver Attack", "C57", "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 f3g5 d7d5 e4d5 f6d5 g5f7", "Aggressive White trap targeting f7.", "Trap"),
            ("Scholar's Mate Trap", "C20", "e2e4 e7e5 d1h5 b8c6 f1c4 g8f6 h5f7", "Classic 4-move checkmate attempt.", "Trap"),
            ("Stafford Gambit", "C42", "e2e4 e7e5 g1f3 g8f6 f3e5 b8c6 e5c6 d7c6", "Black gambits piece activity for quick mating threats.", "Trap"),
            ("Legal's Mate", "C50", "e2e4 e7e5 g1f3 d7d6 f1c4 c7c6 b1c3 c8g4 f3e5 g4d1 c4f7 e7e7 c3d5", "Queen sacrifice leading to a knight/bishop checkmate.", "Trap"),
            ("Sicilian Defense: Najdorf Variation", "B90", "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6", "Popular, sharp counter-attacking defense for Black.", "Opening"),
            ("Queen's Gambit Accepted", "D20", "d2d4 d7d5 c2c4 d5c4 g1f3 g8f6 e2e3", "Solid positional opening for White.", "Opening"),
            ("Caro-Kann Defense", "B12", "e2e4 c7c6 d2d4 d7d5 e2e5 c8f5", "Resilient pawn structure for Black.", "Opening"),
            ("Ruy Lopez: Berlin Defense", "C65", "e2e4 e7e5 g1f3 b8c6 f1c8 b5 g8f6", "Extremely solid endgame-focused response to 1.e4.", "Opening")
        ]
        cursor.executemany("INSERT INTO repertoire (line_name, eco_code, moves_uci, notes, category) VALUES (?, ?, ?, ?, ?)", default_lines)
        conn.commit()
    conn.close()

def is_game_stored(game_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT game_id FROM games WHERE game_id = ?", (game_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def save_game_analysis(game_id, platform, username, acpl, blunders, missed, allowed, pgn, blunder_details, date_played=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not date_played:
        date_played = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute('''
        INSERT OR REPLACE INTO games (game_id, platform, username, date_played, acpl, blunders, missed_tactics, allowed_threats, pgn, analyzed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (game_id, platform, username, date_played, acpl, blunders, missed, allowed, pgn))
    
    for b in blunder_details:
        cursor.execute('''
            INSERT INTO blunders (game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (game_id, b['fen'], b['user_move'], b['best_move'], b['drop'], b['phase'], b['type'], b['move_num'], b['user_color']))
    
    conn.commit()
    conn.close()

def load_all_stats(username):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT acpl, blunders, missed_tactics, allowed_threats, date_played FROM games WHERE username = ? AND analyzed = 1", (username,))
    games = cursor.fetchall()
    
    cursor.execute("SELECT game_id, fen, user_move, best_move, drop_cpl, phase, error_type, move_num, user_color FROM blunders")
    blunders = cursor.fetchall()
    conn.close()
    return games, blunders

def add_repertoire_line(line_name, eco_code, moves_uci, notes="", category="Opening"):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO repertoire (line_name, eco_code, moves_uci, notes, category) VALUES (?, ?, ?, ?, ?)",
                   (line_name, eco_code, moves_uci, notes, category))
    conn.commit()
    conn.close()

def get_repertoire_lines():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, line_name, eco_code, moves_uci, notes, category FROM repertoire")
    lines = cursor.fetchall()
    conn.close()
    return lines
import sqlite3

def init_catalog_db():
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opening_catalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            side TEXT,
            moves TEXT,
            advantages TEXT,
            disadvantages TEXT,
            difficulty TEXT
        )
    ''')
    
    cursor.execute("SELECT COUNT(*) FROM opening_catalog")
    if cursor.fetchone()[0] == 0:
        catalog_data = [
            ("Italian Game", "White", "e2e4 e7e5 g1f3 b8c6 f1c4", "Fast development, pressure on f7", "Black equalizes easily if prepared", "Beginner"),
            ("Queen's Gambit", "White", "d2d4 d7d5 c2c4", "Dominates center, strong positional structure", "Requires patience and positional technique", "Intermediate"),
            ("Sicilian Defense", "Black", "e2e4 c7c5", "Sharp counter-attacks, asymmetrical win odds", "High tactical complexity, heavy theory", "Advanced"),
            ("Caro-Kann Defense", "Black", "e2e4 c7c6 d2d4 d7d5", "Extremely solid, active light-squared bishop", "White gains early space advantage", "Beginner"),
            ("Scandinavian Defense", "Black", "e2e4 d7d5 e4d5 d8d5", "Forces White off-script, easy setup", "White gains tempo by attacking Black's Queen", "Beginner")
        ]
        cursor.executemany("INSERT INTO opening_catalog (name, side, moves, advantages, disadvantages, difficulty) VALUES (?, ?, ?, ?, ?, ?)", catalog_data)
        conn.commit()
    conn.close()

def get_catalog_openings():
    conn = sqlite3.connect("chess_coach.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, side, moves, advantages, disadvantages, difficulty FROM opening_catalog")
    rows = cursor.fetchall()
    conn.close()
    return rows