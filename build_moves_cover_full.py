import sqlite3
import generate_terminal_positions_light as g
import time

DB_NAME = "gobblet_z.db"
RADIX = 1423


def build_top_with_size(a,b,c):
    top=[(0,0)]*9
    for i in range(9):
        if a[i]: top[i]=(a[i],3)
        elif b[i]: top[i]=(b[i],2)
        elif c[i]: top[i]=(c[i],1)
    return top


def can_cover(size,pos,a,b,c):
    _,ts = build_top_with_size(a,b,c)[pos]
    return ts==0 or size>ts


def used(layer,player):
    return sum(1 for x in layer if x==player)


def generate_cover_moves(a,b,c,player):
    for size,layer in [(3,a),(2,b),(1,c)]:
        if used(layer,player)>=2:
            continue
        for pos in range(9):
            if layer[pos]!=0:
                continue
            if not can_cover(size,pos,a,b,c):
                continue

            na,nb,nc=list(a),list(b),list(c)
            if size==3: na[pos]=player
            elif size==2: nb[pos]=player
            else: nc[pos]=player

            yield tuple(na),tuple(nb),tuple(nc)


def main():
    g.build_single_size_states()

    conn=sqlite3.connect(DB_NAME)
    cur=conn.cursor()

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
        PRIMARY KEY(canonical,player)
    );
    """)

    for canon in range(RADIX**3):
        a_idx, b_idx, c_idx = g.unpack_full_index(canon, RADIX)
        a=g._single_size_states[a_idx]
        b=g._single_size_states[b_idx]
        c=g._single_size_states[c_idx]

        for player in (1,2):
            nxt = 2 if player==1 else 1
            cnt=0
            for na,nb,nc in generate_cover_moves(a,b,c,player):
                idx2 = g.pack_full_index(
                    g._single_state_to_index[na],
                    g._single_state_to_index[nb],
                    g._single_state_to_index[nc],
                    RADIX
                )
                canon2 = g.canonical_index(idx2,RADIX)
                cur.execute(
                    "INSERT INTO moves VALUES (?,?,?,?)",
                    (canon,player,canon2,nxt)
                )
                cnt+=1

            cur.execute(
                "INSERT OR REPLACE INTO outdegree VALUES (?,?,?)",
                (canon,player,cnt)
            )

        elapsed = time.time()
        if canon%1000000==0:
            print("processed",canon, "elapsed {elapsed:.1f}s")

    conn.commit()
    conn.close()


if __name__=="__main__":
    main()
