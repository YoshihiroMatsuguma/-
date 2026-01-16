# generate_terminal_positions_light.py

import argparse
import sqlite3
import itertools
import sys
import time

RADIX_FULL = 1423
LINES = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]

_single_size_states = None
_single_state_to_index = None

def build_single_size_states(radix_override=None):
    """Generate all 1423 single-size layer-states (or reduced for test mode)."""
    global _single_size_states, _single_state_to_index
    states = []
    cells = list(range(9))
    max_per_player = 2
    for k in range(0, max_per_player+1):
        for l in range(0, max_per_player+1):
            for pos1 in itertools.combinations(cells, k):
                rem = [c for c in cells if c not in pos1]
                for pos2 in itertools.combinations(rem, l):
                    arr = [0]*9
                    for p in pos1:
                        arr[p] = 1
                    for p in pos2:
                        arr[p] = 2
                    states.append(tuple(arr))
    if radix_override is not None:
        states = states[:radix_override]
    _single_size_states = states
    _single_state_to_index = {s:i for i,s in enumerate(states)}


def pack_full_index(a,b,c,radix):
    return (a * radix + b) * radix + c

def unpack_full_index(idx, radix):
    c = idx % radix
    idx //= radix
    b = idx % radix
    a = idx // radix
    return a,b,c


def build_top_view(a_idx,b_idx,c_idx):
    a = _single_size_states[a_idx]
    b = _single_size_states[b_idx]
    c = _single_size_states[c_idx]
    top = [0]*9
    for i in range(9):
        if a[i] != 0: top[i] = a[i]
        elif b[i] != 0: top[i] = b[i]
        elif c[i] != 0: top[i] = c[i]
        else: top[i] = 0
    return top


def check_winner(top):
    for (i,j,k) in LINES:
        v = top[i]
        if v != 0 and top[j]==v and top[k]==v:
            return v
    return 0


# --------- symmetry definitions ---------
def gen_symmetries():
    perms = []
    def rotate_once(p):
        r = p//3; c = p%3
        return c*3 + (2-r)
    rot1 = [rotate_once(i) for i in range(9)]
    rot2 = [rotate_once(i) for i in rot1]
    rot3 = [rotate_once(i) for i in rot2]
    rots = [list(range(9)), rot1, rot2, rot3]

    def reflect_h(p):
        r = p//3; c = p%3
        return r*3 + (2-c)

    for r in rots:
        perms.append(r)
        perms.append([reflect_h(x) for x in r])

    uniq = []
    seen=set()
    for p in perms:
        t=tuple(p)
        if t not in seen:
            seen.add(t); uniq.append(p)
    return uniq

SYMM = gen_symmetries()


def permute_single_state(state, perm):
    return tuple(state[perm[i]] for i in range(9))


def canonical_index(idx, radix):
    a,b,c = unpack_full_index(idx,radix)
    best=None
    for perm in SYMM:
        a2 = _single_state_to_index[permute_single_state(_single_size_states[a], perm)]
        b2 = _single_state_to_index[permute_single_state(_single_size_states[b], perm)]
        c2 = _single_state_to_index[permute_single_state(_single_size_states[c], perm)]
        v = pack_full_index(a2,b2,c2,radix)
        if best is None or v < best:
            best = v
    return best


# --------- DB ---------------------------------------
def init_db(conn):
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS terminals (
        canonical INTEGER PRIMARY KEY,
        winner INTEGER NOT NULL
    )''')
    conn.commit()


# --------- main scanning loop ------------------------
def scan_slice(conn, radix, a_start, a_end, batch):
    cur = conn.cursor()
    t0 = time.time()
    total = (a_end - a_start) * radix * radix
    seen = 0
    to_insert = []

    for a in range(a_start, a_end):
        for b in range(radix):
            for c in range(radix):
                idx = pack_full_index(a,b,c,radix)
                top = build_top_view(a,b,c)
                w = check_winner(top)
                seen += 1

                if w != 0:
                    canon = canonical_index(idx,radix)
                    to_insert.append((canon,w))

                if len(to_insert) >= batch:
                    cur.executemany('INSERT OR IGNORE INTO terminals(canonical,winner) VALUES(?,?)', to_insert)
                    conn.commit()
                    to_insert = []
                    elapsed = time.time()-t0
                    print(f"scanned {seen}/{total}, elapsed {elapsed:.1f}s")

    if to_insert:
        cur.executemany('INSERT OR IGNORE INTO terminals(canonical,winner) VALUES(?,?)', to_insert)
        conn.commit()

    print(f"slice [{a_start},{a_end}) done: scanned {seen}")


# --------- CLI ---------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', required=True)
    parser.add_argument('--a-start', type=int, default=0)
    parser.add_argument('--a-end', type=int, default=RADIX_FULL)
    parser.add_argument('--batch', type=int, default=200000)
    parser.add_argument('--test-small', action='store_true')
    args = parser.parse_args()

    RADIX = 50 if args.test_small else RADIX_FULL
    if args.a_start<0 or args.a_end>RADIX or args.a_start>=args.a_end:
        print("Invalid range for a-start/a-end")
        sys.exit(1)

    print(f"Using RADIX={RADIX}")
    build_single_size_states(radix_override=RADIX)

    conn = sqlite3.connect(args.db, timeout=30)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')

    init_db(conn)

    scan_slice(conn, RADIX, args.a_start, args.a_end, args.batch)
    conn.close()


if __name__=='__main__':
    main()
