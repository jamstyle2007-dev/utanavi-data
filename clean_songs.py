#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""songs.json の自動追加分（iTunes由来・year>=2025）を洗い直す。

問題（2026-08-22 監査）: 2,190曲中 2,189曲が場面/ムード空（有料機能に出ない）、重複257、別バージョン172、
曲名とアーティストの入れ替わり105、DAM/JOYSOUND が確認なしで全部 true。

やること:
  1. 入れ替わり（曲名が既存アーティスト名と一致）・重複・別バージョン（feat./TVサイズ/remix等）を除去
  2. 残った新曲に 場面/ムード/エネルギー/難易度 を、そのアーティストの既存曲（手作り分）から継承
  3. DAM/JOYSOUND は確認できないので null（未確認）にする
手作りのベース曲（year<2025 または scenes入り）は一切触らない。

usage: python3 clean_songs.py [--write]
"""
import json, re, sys, collections

PATH = "songs.json"
ALT = re.compile(r"feat\.?|ft\.|remix|リミックス|ver\.|version|バージョン|edit|\bmix\b|acoustic|アコースティック|tv size|tvサイズ|short ver|full ver|instrumental|inst\.|karaoke|カラオケ|off vocal|live|ライブ|ライヴ|piano|ピアノ|english ver|japanese ver|korean ver|2\d{3} ver|\(from|\[from|- from|movie|映画|radio edit", re.I)

def na(a):
    a = a.lower()
    a = re.split(r"feat|／|/| x |×|（|\(|&|,", a)[0]
    return re.sub(r"\s+", "", a)

def nt(t):
    t = re.sub(r"[（(].*?[)）]", "", t)
    t = re.sub(r"[\[【].*?[\]】]", "", t)
    return re.sub(r"[\s・〜~,.!?’'\-－―]", "", t.lower())

def main(write=False):
    songs = json.load(open(PATH, encoding="utf-8"))
    base = [s for s in songs if (s.get("year") or 0) < 2025 or s.get("scenes")]
    auto = [s for s in songs if s not in base]
    print(f"総曲数 {len(songs)} / ベース {len(base)} / 自動追加 {len(auto)}")

    artist_names = {na(s["artist"]) for s in base}
    artist_titles = {na(s["artist"]): s["artist"] for s in base}
    # アーティストごとの属性プロファイル（継承元）
    prof = {}
    for s in base:
        p = prof.setdefault(na(s["artist"]), {"scenes": collections.Counter(), "moods": collections.Counter(),
                                               "tags": collections.Counter(), "energy": [], "difficulty": [],
                                               "genre": collections.Counter(), "voice": collections.Counter()})
        p["scenes"].update(s.get("scenes") or []); p["moods"].update(s.get("moods") or [])
        p["tags"].update(t for t in (s.get("tags") or []) if not re.search(r"年代|令和|平成|昭和|邦楽|洋楽", t))
        if s.get("energy"): p["energy"].append(s["energy"])
        if s.get("difficulty"): p["difficulty"].append(s["difficulty"])
        p["genre"][s.get("genre")] += 1; p["voice"][s.get("voice")] += 1

    seen = {nt(s["title"]) + "|" + na(s["artist"]) for s in base}
    kept, dropped = [], collections.Counter()
    for s in auto:
        t, a = s["title"], s["artist"]
        if na(t) in artist_names:                 # 曲名が既存アーティスト名 → 入れ替わり
            dropped["入れ替わり"] += 1; continue
        if na(a) not in prof:                     # 既存アーティスト以外（検索の巻き込み）
            dropped["既存アーティスト外"] += 1; continue
        if ALT.search(t):                         # 別バージョン
            dropped["別バージョン"] += 1; continue
        k = nt(t) + "|" + na(a)
        if k in seen:                             # 重複
            dropped["重複"] += 1; continue
        seen.add(k)
        p = prof[na(a)]
        s2 = dict(s)
        s2["artist"] = artist_titles[na(a)]       # 表記をベースに揃える
        s2["scenes"] = [x for x, _ in p["scenes"].most_common(3)] or ["みんなで"]
        s2["moods"] = [x for x, _ in p["moods"].most_common(2)] or ["定番"]
        ex = [x for x, _ in p["tags"].most_common(3)]
        s2["tags"] = list(dict.fromkeys((s.get("tags") or []) + ["最新曲"] + ex))
        s2["energy"] = round(sum(p["energy"]) / len(p["energy"])) if p["energy"] else 3
        s2["difficulty"] = round(sum(p["difficulty"]) / len(p["difficulty"])) if p["difficulty"] else 3
        s2["genre"] = p["genre"].most_common(1)[0][0] or s.get("genre")
        s2["voice"] = p["voice"].most_common(1)[0][0] or s.get("voice")
        s2["dam"] = None; s2["joysound"] = None   # 未確認
        kept.append(s2)

    print("除去:", dict(dropped), "| 残した新曲:", len(kept))
    out = base + kept
    ids = collections.Counter(s["id"] for s in out)
    assert max(ids.values()) == 1, "id重複"
    if write:
        json.dump(out, open(PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=None, separators=(",", ":"))
        print(f"書き込み: {len(out)}曲")
    return out

if __name__ == "__main__":
    main("--write" in sys.argv)
