import sqlite3
from collections import deque
import generate_terminal_positions_light as g

DB = "retrograde.sqlite"
TERM_DB = "gobblet_z.db"
RADIX = g.RADIX_FULL


# ---------- 初期化 ----------

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.executescript("""
    PRAGMA journal_mode=WAL;
    PRAGMA synchronous=NORMAL;

    CREATE TABLE IF NOT EXISTS states(
        canon INTEGER,
        player INTEGER,
        value INTEGER,
        depth INTEGER,
        remaining INTEGER,
        PRIMARY KEY(canon, player)
    );

    CREATE TABLE IF NOT EXISTS queue(
        canon INTEGER,
        player INTEGER,
        depth INTEGER
    );
    """)
    conn.commit()
    return conn


# ---------- 終局登録 ----------

def load_terminals(conn):
    g.build_single_size_states()

    cur = conn.cursor()
    tconn = sqlite3.connect(TERM_DB)
    tcur = tconn.cursor()

    for canon, winner in tcur.execute("SELECT canonical, winner FROM terminals"):
        loser = 2 if winner == 1 else 1
        cur.execute(
            "INSERT OR IGNORE INTO states VALUES (?,?,?,?,?)",
            (canon, loser, -1, 0, 0)
        )
        cur.execute(
            "INSERT INTO queue VALUES (?,?,?)",
            (canon, loser, 0)
        )

    conn.commit()
    tconn.close()


# ---------- forward 合法手数 ----------

def count_forward_moves(canon, player):
    a, b, c = g.unpack_full_index(canon, RADIX)
    layers = [
        list(g._single_size_states[a]),
        list(g._single_size_states[b]),
        list(g._single_size_states[c]),
    ]

    used = [sum(1 for x in layers[i] if x == player) for i in range(3)]
    moves = 0

    for size in range(3):
        if used[size] >= 2:
            continue
        for pos in range(9):
            if any(layers[u][pos] != 0 for u in range(size)):
                continue
            if layers[size][pos] == 0:
                moves += 1
    return moves


# ---------- 逆合法手生成 ----------

def generate_predecessors(canon, prev_player):
    preds = []
    a, b, c = g.unpack_full_index(canon, RADIX)
    layers = [
        list(g._single_size_states[a]),
        list(g._single_size_states[b]),
        list(g._single_size_states[c]),
    ]

    top = g.build_top_view(a, b, c)

    for (i, j, k) in g.LINES:
        if top[i] == top[j] == top[k] == prev_player:
            for pos in (i, j, k):
                for size in range(3):
                    if layers[size][pos] == prev_player:
                        new_layers = [l.copy() for l in layers]
                        new_layers[size][pos] = 0

                        na, nb, nc = map(tuple, new_layers)
                        if na in g._single_state_to_index \
                           and nb in g._single_state_to_index \
                           and nc in g._single_state_to_index:
                            idx = g.pack_full_index(
                                g._single_state_to_index[na],
                                g._single_state_to_index[nb],
                                g._single_state_to_index[nc],
                                RADIX
                            )
                            preds.append(g.canonical_index(idx, RADIX))
                        break
    return preds


# ---------- 後退解析 ----------

def retrograde(conn):
    cur = conn.cursor()

    while True:
        row = cur.execute(
            "SELECT canon, player, depth FROM queue LIMIT 1"
        ).fetchone()

        if row is None:
            break

        canon, player, depth = row
        cur.execute("DELETE FROM queue WHERE canon=? AND player=?",
                    (canon, player))

        prev_player = 2 if player == 1 else 1

        for prev in generate_predecessors(canon, prev_player):
            r = cur.execute(
                "SELECT value, remaining FROM states WHERE canon=? AND player=?",
                (prev, prev_player)
            ).fetchone()

            if r is not None:
                continue

            cur.execute(
                "INSERT OR IGNORE INTO states VALUES (?,?,?,?,?)",
                (prev, prev_player, 0, -1,
                 count_forward_moves(prev, prev_player))
            )

            cur.execute(
                "UPDATE states SET remaining = remaining - 1 "
                "WHERE canon=? AND player=?",
                (prev, prev_player)
            )

            rem = cur.execute(
                "SELECT remaining FROM states WHERE canon=? AND player=?",
                (prev, prev_player)
            ).fetchone()[0]

            if rem == 0:
                cur.execute(
                    "UPDATE states SET value=-1, depth=? "
                    "WHERE canon=? AND player=?",
                    (depth + 1, prev, prev_player)
                )
                cur.execute(
                    "INSERT INTO queue VALUES (?,?,?)",
                    (prev, prev_player, depth + 1)
                )

        conn.commit()


# ---------- main ----------

if __name__ == "__main__":
    conn = init_db()
    load_terminals(conn)
    retrograde(conn)
    conn.close()
