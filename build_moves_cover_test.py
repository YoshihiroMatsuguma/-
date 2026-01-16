# build_moves_cover.py
import sqlite3
import generate_terminal_positions_light as g

# 最初は必ず test-small
RADIX = 50
DB_NAME = "gobblet_test.db"


# ---------------- トップ（サイズ付き） ----------------
def build_top_with_size(a, b, c):
    """
    各マスについて (player, size) を返す
    size: 3=Large, 2=Medium, 1=Small, 0=empty
    """
    top = [(0, 0)] * 9
    for i in range(9):
        if a[i] != 0:
            top[i] = (a[i], 3)
        elif b[i] != 0:
            top[i] = (b[i], 2)
        elif c[i] != 0:
            top[i] = (c[i], 1)
    return top


def can_cover(size, pos, a, b, c):
    """
    size の駒を pos に「かぶせて」置けるか
    """
    _, top_size = build_top_with_size(a, b, c)[pos]
    return top_size == 0 or size > top_size


def used_count(layer, player):
    """
    そのサイズで player が使っている駒の数
    """
    return sum(1 for x in layer if x == player)


# ---------------- かぶせ手のみの合法手生成 ----------------
def generate_cover_moves(a, b, c, player):
    """
    未使用の駒を置く／かぶせる手のみ
    移動は含まない
    """
    for size, layer in [(3, a), (2, b), (1, c)]:
        if used_count(layer, player) >= 2:
            continue

        for pos in range(9):
            if layer[pos] != 0:
                continue
            if not can_cover(size, pos, a, b, c):
                continue

            na = list(a)
            nb = list(b)
            nc = list(c)

            if size == 3:
                na[pos] = player
            elif size == 2:
                nb[pos] = player
            else:
                nc[pos] = player

            yield tuple(na), tuple(nb), tuple(nc)


# ---------------- メイン ----------------
def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # テーブル作成
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS moves(
        from_canonical INTEGER,
        from_player INTEGER,
        to_canonical INTEGER,
        to_player INTEGER
    );

    CREATE TABLE IF NOT EXISTS outdegree(
        canonical INTEGER,
        player INTEGER,
        count INTEGER,
        PRIMARY KEY (canonical, player)
    );
    """)

    g.build_single_size_states(radix_override=RADIX)

    print("Building cover-only moves...")

    for canon in range(RADIX ** 3):
        a_idx, b_idx, c_idx = g.unpack_full_index(canon, RADIX)

        a = g._single_size_states[a_idx]
        b = g._single_size_states[b_idx]
        c = g._single_size_states[c_idx]

        for player in (1, 2):
            next_player = 2 if player == 1 else 1
            cnt = 0

            for na, nb, nc in generate_cover_moves(a, b, c, player):
                if (na not in g._single_state_to_index or
                    nb not in g._single_state_to_index or
                    nc not in g._single_state_to_index):
                    continue

                idx2 = g.pack_full_index(
                    g._single_state_to_index[na],
                    g._single_state_to_index[nb],
                    g._single_state_to_index[nc],
                    RADIX
                )
                canon2 = idx2

                cur.execute(
                    "INSERT INTO moves VALUES (?, ?, ?, ?)",
                    (canon, player, canon2, next_player)
                )
                cnt += 1

            cur.execute(
                "INSERT OR REPLACE INTO outdegree VALUES (?, ?, ?)",
                (canon, player, cnt)
            )

        # 進捗表示（任意）
        if canon % 50000 == 0:
            print(f"  processed canon = {canon}")

    conn.commit()
    conn.close()
    print("build_moves_cover.py finished successfully.")


if __name__ == "__main__":
    main()
