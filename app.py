import streamlit as st
import pandas as pd
import plotly.express as px
import streamlit.components.v1 as components
import chess

from db_manager import (
    init_db, 
    load_all_stats, 
    save_game_analysis, 
    is_game_stored, 
    add_repertoire_line, 
    get_repertoire_lines,
    get_catalog_openings,
    init_catalog_db
)
from chess_analyzer import (
    fetch_chess_com_games, 
    fetch_lichess_games, 
    fetch_lichess_study_pgn,
    analyze_games_local, 
    generate_llm_report,
    ask_ai_coach,
    calculate_elo_change
)

st.set_page_config(page_title="OpenChessCoach", page_icon="♟️", layout="wide", initial_sidebar_state="expanded")

# Initialize Databases
init_db()
init_catalog_db()

# Convert UCI moves to Standard Algebraic Notation (e.g., e7f6 -> exf6 or Qf7)
def uci_to_san(fen, uci_move):
    if not uci_move or uci_move == "N/A":
        return uci_move
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci_move)
        return board.san(move)
    except Exception:
        return uci_move

# Custom UI Theme Stylesheet
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    :root {
        --bg-dark: #0B0E14;
        --card-bg: #151921;
        --card-border: #232936;
        --accent-blue: #0066FF;
        --accent-cyan: #00F0FF;
        --accent-glow: rgba(0, 102, 255, 0.35);
        --text-primary: #F0F4F8;
        --text-muted: #8A94A6;
        --radius: 12px;
    }

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
        background-color: var(--bg-dark);
        color: var(--text-primary);
    }

    .stApp {
        background-color: var(--bg-dark);
    }

    section[data-testid="stSidebar"] {
        background-color: #10131B !important;
        border-right: 1px solid var(--card-border) !important;
    }

    .hero-banner {
        background: linear-gradient(135deg, rgba(0, 102, 255, 0.12) 0%, rgba(0, 240, 255, 0.05) 100%);
        border: 1px solid var(--card-border);
        border-radius: var(--radius);
        padding: 24px 32px;
        margin-bottom: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
    }

    div[data-testid="stMetric"] {
        background: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: var(--radius) !important;
        padding: 18px 22px !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25) !important;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }

    div[data-testid="stMetric"]:hover {
        border-color: var(--accent-blue) !important;
        transform: translateY(-2px);
    }

    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, var(--accent-blue) 0%, #0040CC 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: var(--radius) !important;
        font-weight: 600 !important;
        padding: 0.65rem 1.4rem !important;
        box-shadow: 0 0 20px var(--accent-glow) !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }

    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 0 30px rgba(0, 240, 255, 0.6) !important;
        transform: translateY(-2px);
    }

    div.stButton > button[kind="secondary"] {
        background-color: var(--card-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: var(--radius) !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    div.stButton > button[kind="secondary"]:hover {
        border-color: var(--accent-blue) !important;
        color: var(--accent-cyan) !important;
    }

    div[data-baseweb="input"], div[data-baseweb="select"] {
        border-radius: 10px !important;
        background-color: #10131B !important;
        border: 1px solid var(--card-border) !important;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        border-bottom: 1px solid var(--card-border);
        padding-bottom: 8px;
    }

    .stTabs [data-baseweb="tab"] {
        height: 44px;
        background-color: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 10px;
        color: var(--text-muted);
        font-weight: 600;
        padding: 0px 20px;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(0, 102, 255, 0.2) 0%, rgba(0, 240, 255, 0.1) 100%) !important;
        color: var(--text-primary) !important;
        border-color: var(--accent-blue) !important;
    }

    .stExpander {
        background-color: var(--card-bg) !important;
        border: 1px solid var(--card-border) !important;
        border-radius: var(--radius) !important;
    }
</style>
""", unsafe_allow_html=True)

# Dashboard Hero Banner
st.markdown("""
<div class="hero-banner">
    <h2 style="margin:0; font-weight:700; color:#F0F4F8;">OpenChessCoach Workspace</h2>
    <p style="margin:4px 0 0 0; color:#8A94A6; font-size:14px;">Next-Generation Game Analytics & Interactive AI Repertoire Studio</p>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
with st.sidebar:
    st.markdown("### :material/settings: Configuration")
    username = st.text_input("Player Handle", value="1qschool1", key="sb_user_input")
    platform = st.selectbox("Platform Source", ["Chess.com", "Lichess"], key="sb_platform_select")
    game_count = st.slider("Sync Depth (Games)", min_value=1, max_value=100, value=10, step=5, key="sb_count_slider")
    
    st.divider()
    st.markdown("### :material/smart_toy: AI Provider Engine")
    llm_provider = st.selectbox(
        "Provider", 
        ["None (Disabled)", "Ollama (Local)", "OpenRouter", "Omniroute", "Gemini (Cloud)", "OpenAI (Cloud)"],
        key="sb_provider_select"
    )
    
    api_key = ""
    custom_url = ""
    if llm_provider not in ["None (Disabled)", "Ollama (Local)"]:
        api_key = st.text_input("API Key", type="password", key="sb_key_input")
    if llm_provider in ["Omniroute", "Ollama (Local)"]:
        custom_url = st.text_input("Custom Base URL", value="", key="sb_url_input")

    st.divider()
    run_btn = st.button("Run Stockfish Engine", type="primary", icon=":material/analytics:", use_container_width=True, key="sb_run_sidebar")
    db_load_btn = st.button("Load Local Database", type="secondary", icon=":material/database:", use_container_width=True, key="sb_load_sidebar")

# Interactive Chessboard Component Renderer
def render_interactive_board(fen, orientation="white", best_move_uci="", element_id="board"):
    best_move_san = uci_to_san(fen, best_move_uci) if best_move_uci else ""

    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <link rel="stylesheet" href="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css">
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <script src="https://unpkg.com/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"></script>
        <style>
            body {{ margin: 0; padding: 10px; background-color: transparent; font-family: sans-serif; }}
            #{element_id} {{ width: 340px; height: 340px; margin: 0 auto; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.4); }}
            .status-text {{ text-align: center; font-size: 13px; font-weight: 600; color: #8A94A6; margin-top: 12px; }}
        </style>
    </head>
    <body>
        <div id="{element_id}"></div>
        <div id="status_{element_id}" class="status-text">Drag pieces to play move</div>

        <script>
            window.onload = function() {{
                try {{
                    var game = new Chess('{fen}');
                    var targetUci = '{best_move_uci}';
                    var targetSan = '{best_move_san}';

                    function onDrop (source, target) {{
                        var move = game.move({{ from: source, to: target, promotion: 'q' }});
                        if (move === null) return 'snapback';

                        var playedUci = source + target + (move.promotion ? move.promotion : '');
                        
                        if (targetUci && (playedUci === targetUci || move.san === targetSan)) {{
                            $('#status_{element_id}').css('color', '#00F0FF').text('🎯 Perfect! Played ' + move.san);
                        }} else if (targetUci) {{
                            $('#status_{element_id}').css('color', '#FF4D4D').text('❌ Played ' + move.san + '. Best move: ' + targetSan);
                            setTimeout(function() {{ game.undo(); board.position(game.fen()); }}, 1200);
                        }}
                    }}

                    var board = Chessboard('{element_id}', {{
                        draggable: true,
                        position: '{fen}',
                        orientation: '{orientation}',
                        pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{{piece}}.png',
                        onDrop: onDrop
                    }});
                }} catch (err) {{
                    console.error("Chessboard render error:", err);
                }}
            }};
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=410)

# Database Actions
if db_load_btn:
    games_data, blunders_data = load_all_stats(username)
    if games_data:
        total_g = len(games_data)
        avg_acpl = round(sum(g[0] for g in games_data) / max(1, total_g), 1)
        tot_blunders = sum(g[1] for g in games_data)

        blunder_list = [{
            "game_num": b[0], "fen": b[1], "user_move": b[2], "best_move": b[3],
            "drop": b[4], "phase": b[5], "type": b[6], "move_num": b[7], "user_color": b[8]
        } for b in blunders_data]

        st.session_state["report_data"] = {
            "username": username,
            "total_games": total_g,
            "acpl": avg_acpl,
            "total_blunders": tot_blunders,
            "blunders_missed": sum(g[2] for g in games_data),
            "blunders_allowed": sum(g[3] for g in games_data),
            "blunders_by_phase": {"opening": 2, "middlegame": 5, "endgame": 3},
            "move_qualities": {"Best": 120, "Good": 80, "Inaccuracy": 20, "Mistake": 10, "Blunder": tot_blunders},
            "rating_dna": {"Opening Precision": 75, "Tactical Vision": 65, "Endgame Technique": 80, "Threat Awareness": 70, "Consistency": 72},
            "blunder_details": blunder_list,
            "game_history": [{"game": idx + 1, "acpl": g[0]} for idx, g in enumerate(games_data)]
        }
        st.session_state["coach_brief"] = generate_llm_report(st.session_state["report_data"], provider=llm_provider, api_key=api_key, custom_base_url=custom_url)
        st.sidebar.success(f"Synchronized {total_g} records from local database.")
    else:
        st.sidebar.error("No database records found for this user.")

if run_btn:
    with st.spinner(f"Analyzing {game_count} games with Stockfish engine..."):
        games = fetch_chess_com_games(username, count=game_count) if platform == "Chess.com" else fetch_lichess_games(username, count=game_count)
        STOCKFISH_PATH = "stockfish-windows-x86-64-avx2.exe"
        report_data = analyze_games_local(games, username, STOCKFISH_PATH, depth=15)
        
        for idx, g in enumerate(games):
            game_id = g.headers.get("Link", f"{username}_{idx}")
            if not is_game_stored(game_id):
                save_game_analysis(game_id, platform, username, report_data["acpl"], report_data["total_blunders"],
                                   report_data["blunders_missed"], report_data["blunders_allowed"], str(g), report_data["blunder_details"])
        
        st.session_state["report_data"] = report_data
        st.session_state["coach_brief"] = generate_llm_report(report_data, provider=llm_provider, api_key=api_key, custom_base_url=custom_url)

# Navigation Tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    ":material/bar_chart: Performance & DNA", 
    ":material/psychology: AI Coach Chat", 
    ":material/extension: Personal Puzzles", 
    ":material/menu_book: Openings & Catalog", 
    ":material/calculate: Elo Rating Tool"
])

# Tab 1: Performance & Rating DNA
with tab1:
    if "report_data" in st.session_state:
        data = st.session_state["report_data"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Games Processed", data["total_games"])
        c2.metric("Average ACPL", data["acpl"])
        c3.metric("Blunders Recorded", data["total_blunders"])
        c4.metric("Tactics Missed", data["blunders_missed"])

        st.markdown("<br>", unsafe_allow_html=True)

        col_dna, col_mq = st.columns(2)
        with col_dna:
            st.markdown("#### :material/fingerprint: Rating DNA Archetype")
            dna_stats = data.get("rating_dna", {})
            dna_df = pd.DataFrame(list(dna_stats.items()), columns=["Attribute", "Score"])
            fig_radar = px.line_polar(dna_df, r="Score", theta="Attribute", line_close=True, range_r=[0, 100])
            fig_radar.update_traces(fill="toself", fillcolor="rgba(0, 102, 255, 0.25)", line_color="#00F0FF")
            fig_radar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#F0F4F8")
            st.plotly_chart(fig_radar, use_container_width=True)

        with col_mq:
            st.markdown("#### :material/pie_chart: Move Quality Distribution")
            mq = data.get("move_qualities", {})
            mq_df = pd.DataFrame(list(mq.items()), columns=["Quality", "Count"])
            fig_mq = px.pie(mq_df, names="Quality", values="Count", hole=0.5, color="Quality",
                            color_discrete_map={"Best":"#2ecc71", "Good":"#3498db", "Inaccuracy":"#f1c40f", "Mistake":"#e67e22", "Blunder":"#e74c3c"})
            fig_mq.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#F0F4F8")
            st.plotly_chart(fig_mq, use_container_width=True)

        st.markdown("#### :material/verified: Strategic AI Briefing")
        st.info(st.session_state.get("coach_brief", "No report generated."))
    else:
        st.info("Initiate Stockfish analysis or load local database records from the sidebar.")

# Tab 2: Interactive AI Coach Chat
with tab2:
    st.markdown("#### :material/chat: Personal AI Performance Assistant")
    st.caption("Ask questions about your playing patterns, blunders, win rates, and weekly trends.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("Ask your coach (e.g., 'What are my main weaknesses in the endgame?')")
    if user_query:
        st.session_state["chat_history"].append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        with st.chat_message("assistant"):
            current_data = st.session_state.get("report_data", {"username": username})
            answer = ask_ai_coach(user_query, current_data, provider=llm_provider, api_key=api_key, custom_base_url=custom_url)
            st.markdown(answer)
            st.session_state["chat_history"].append({"role": "assistant", "content": answer})

# Tab 3: Personal Puzzles
with tab3:
    if "report_data" in st.session_state and st.session_state["report_data"].get("blunder_details"):
        blunders = st.session_state["report_data"]["blunder_details"]
        st.markdown("#### :material/grid_view: Custom Game Tactics")

        blunder_idx = st.number_input("Puzzle Index", min_value=1, max_value=len(blunders), value=1, key="puz_select") - 1
        selected = blunders[blunder_idx]

        col_board, col_info = st.columns([1, 1])

        with col_board:
            render_interactive_board(
                selected["fen"], 
                selected["user_color"], 
                selected["best_move"], 
                f"puzzle_board_{blunder_idx}"
            )

        with col_info:
            user_san = uci_to_san(selected["fen"], selected["user_move"])
            best_san = uci_to_san(selected["fen"], selected["best_move"])

            st.markdown(f"**Move Number:** {selected['move_num']} ({selected['phase'].capitalize()})")
            st.markdown(f"**Error Classification:** {selected['type']}")
            st.error(f"**Your Play:** `{user_san}` (CPL: -{selected['drop']})")
            st.success(f"**Recommended Move:** `{best_san}`")
    else:
        st.info("No blunders extracted yet. Run game engine evaluation.")

# Tab 4: Openings & Catalog
with tab4:
    st.markdown("#### :material/library_books: Openings, Traps & Lichess Study Importer")
    
    col_study, col_cat = st.columns(2)
    with col_study:
        st.markdown("**Import Lichess Study**")
        study_url = st.text_input("Lichess Study URL", placeholder="https://lichess.org/study/PXUWCtku", key="study_url_input")
        if st.button("Import Study Chapters", type="primary", icon=":material/download:", key="btn_import_study"):
            if study_url:
                chapters = fetch_lichess_study_pgn(study_url)
                for ch in chapters:
                    add_repertoire_line(ch[0], ch[1], ch[2], ch[3], category="Lichess Study")
                st.success(f"Successfully imported {len(chapters)} study chapters.")
            else:
                st.error("Provide a valid Lichess study URL.")

    with col_cat:
        st.markdown("**Catalog Explorer**")
        catalog = get_catalog_openings()
        diff_filter = st.selectbox("Difficulty Filter", ["All", "Beginner", "Intermediate", "Advanced"], key="cat_diff_filter")

    st.divider()

    st.markdown("#### :material/folder: Pre-built Opening Library")
    for item in catalog:
        item_id, name, side, moves, adv, disadv, diff = item
        if diff_filter == "All" or diff_filter == diff:
            with st.expander(f"{name} ({side}) — {diff}"):
                st.write(f"**Sequence (UCI):** `{moves}`")
                st.write(f":material/check_circle: **Advantages:** {adv}")
                st.write(f":material/cancel: **Disadvantages:** {disadv}")
                if st.button(f"Add {name} to Practice", icon=":material/add:", key=f"add_cat_{item_id}"):
                    add_repertoire_line(name, "ECO", moves, f"Advantages: {adv} | Disadvantages: {disadv}")
                    st.success(f"Added {name} to your repertoire.")

    st.divider()
    stored_lines = get_repertoire_lines()
    if stored_lines:
        st.markdown("#### :material/model_training: Active Flashcard Repertoire")
        line_names = [f"[{l[5]}] {l[1]} ({l[2]})" for l in stored_lines]
        selected_line_idx = st.selectbox("Active Practice Line", range(len(line_names)), format_func=lambda x: line_names[x], key="rep_select")
        chosen = stored_lines[selected_line_idx]

        st.caption(f"Notes: {chosen[4] or 'No custom notes provided.'}")
        moves_list = chosen[3].split()
        
        rep_board = chess.Board()
        for m in moves_list:
            try:
                rep_board.push_uci(m)
            except Exception:
                pass

        render_interactive_board(
            rep_board.fen(), 
            "white", 
            moves_list[-1] if moves_list else "", 
            f"rep_practice_board_{selected_line_idx}"
        )

# Tab 5: Elo Calculator
with tab5:
    st.markdown("#### :material/calculate: Elo Rating Gain/Loss Calculator")
    c1, c2, c3 = st.columns(3)
    user_r = c1.number_input("Your Rating", value=1100, key="elo_user_input")
    opp_r = c2.number_input("Opponent Rating", value=1150, key="elo_opp_input")
    result_val = c3.selectbox("Game Outcome", ["Win (1.0)", "Draw (0.5)", "Loss (0.0)"], key="elo_res_select")

    num_result = 1.0 if "Win" in result_val else (0.5 if "Draw" in result_val else 0.0)
    new_rating, change = calculate_elo_change(user_r, opp_r, num_result)

    if change >= 0:
        st.success(f"Projected Rating: **{new_rating}** (+{change} Elo)")
    else:
        st.error(f"Projected Rating: **{new_rating}** ({change} Elo)")