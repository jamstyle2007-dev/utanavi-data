#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
カラオケ選曲ナビ — 月次データ更新（GitHub Actions から月1回実行。手動実行も可）。

  1) songs.json : 既存アーティストの新曲（直近2年）を iTunes Search から"検証付き"で追記
  2) hot.json   : Apple Music Japan「トップソング」TOP100 を取得し、songs.json の実曲に解決

2026-08-22 の監査で、旧版は検索の巻き込み（別アーティスト）・曲名とアーティストの入れ替わり・
別バージョン・重複を大量に取り込み、場面/ムードが空で有料機能に出ず、DAM/JOY を確認なしに true に
していた。以後は次を必ず守る（clean_songs.py と同じ基準）:

  - アーティスト名は正規化して"完全一致"したものだけ採用（巻き込み禁止）
  - 曲名が既存アーティスト名と一致するものは捨てる（入れ替わり）
  - feat./remix/TVサイズ/live/ピアノ 等の別バージョンは捨てる
  - 既存曲との重複（正規化キー）は捨てる
  - 場面/ムード/エネルギー/難易度/ジャンル/声域は、そのアーティストの手作り曲から継承
  - DAM/JOYSOUND は確認できないので null（未確認）。true にしない
  - 1アーティスト最大 5曲 / 1回最大 300曲（控えめ）
  - TOP100 のうち既存アーティストの未収録曲は、上の検証を通った上で songs.json に追加する

usage: python3 update_songs.py [--no-songs] [--no-hot]
"""
import json, re, sys, time, urllib.parse, urllib.request, urllib.error, datetime, collections

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
SONGS = HERE + "/songs.json"
HOT = HERE + "/hot.json"
TODAY = datetime.date.today()
MIN_YEAR = TODAY.year - 1
MAX_NEW_TOTAL = 300
PER_ARTIST_CAP = 5
UA = "Mozilla/5.0"
RSS = "https://rss.marketingtools.apple.com/api/v2/jp/music/most-played/100/songs.json"

ALT = re.compile(r"feat\.?|ft\.|remix|リミックス|ver\.|version|バージョン|edit|\bmix\b|acoustic|アコースティック|tv size|tvサイズ|short ver|full ver|instrumental|inst\.|karaoke|カラオケ|off vocal|\blive\b|ライブ|ライヴ|piano|ピアノ|english ver|japanese ver|korean ver|2\d{3} ver|\(from|\[from|- from|movie|映画|radio edit|オルゴール|cover|カバー|\bbgm\b|作業用|demo|デモ|medley|メドレー|sped up|slowed", re.I)
GENL = {"jpop":"邦楽","anime":"アニソン","vocaloid":"ボカロ","band":"バンド","western":"洋楽","kpop":"K-POP","chinese":"華語","enka":"演歌・昭和"}

def na(a):
    a = a.lower()
    a = re.split(r"feat|／|/| x |×|（|\(|&|,", a)[0]
    return re.sub(r"\s+", "", a)
def nt(t):
    t = re.sub(r"[（(].*?[)）]", "", t)
    t = re.sub(r"[\[【].*?[\]】]", "", t)
    return re.sub(r"[\s・〜~,.!?’'\-－―]", "", t.lower())
def key(t, a): return nt(t) + "|" + na(a)
def dtag(y): return "〜60年代前" if y < 1960 else (f"{(y//10)*10}年代" if y >= 2000 else f"{(y//10)*10%100}年代")
def etag(y): return "令和" if y >= 2019 else ("平成" if y >= 1989 else "昭和")
def slug(t, a): return (re.sub(r"[^a-z0-9]+", "-", (t + "-" + a).lower()).strip("-")[:40]) or "song"

REQ_INTERVAL = 3.2   # iTunes Search API は約20req/分で 429→403(一時ブロック) になるため直列・間隔あり
_last_req = [0.0]
def fetch_json(url, tries=3):
    err = None
    for k in range(tries):
        wait = REQ_INTERVAL - (time.time() - _last_req[0])
        if wait > 0: time.sleep(wait)
        try:
            _last_req[0] = time.time()
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            err = e
            if e.code in (429, 403): time.sleep(60 * (k + 1))   # レート制限は長めに待つ
            else: time.sleep(2)
        except Exception as e:
            err = e; time.sleep(2)
    print("  fetch失敗:", url[:90], err); return None

def itunes_artist(artist):
    url = ("https://itunes.apple.com/search?term=" + urllib.parse.quote(artist) +
           "&country=JP&media=music&entity=song&attribute=artistTerm&limit=200")
    return (fetch_json(url) or {}).get("results", [])

# ---------------------------------------------------------------- プロファイル（継承元）
class Catalog:
    def __init__(self, songs):
        self.songs = songs
        self.base = [s for s in songs if (s.get("year") or 0) < 2025 or s.get("scenes")]
        self.artist_names = {na(s["artist"]) for s in songs}
        self.artist_disp = {}
        self.prof = {}
        for s in self.base:
            k = na(s["artist"])
            self.artist_disp.setdefault(k, s["artist"])
            p = self.prof.setdefault(k, {"scenes": collections.Counter(), "moods": collections.Counter(),
                                         "tags": collections.Counter(), "energy": [], "difficulty": [],
                                         "genre": collections.Counter(), "voice": collections.Counter()})
            p["scenes"].update(s.get("scenes") or []); p["moods"].update(s.get("moods") or [])
            p["tags"].update(t for t in (s.get("tags") or []) if not re.search(r"年代|令和|平成|昭和|邦楽|洋楽|最新曲", t))
            if s.get("energy"): p["energy"].append(s["energy"])
            if s.get("difficulty"): p["difficulty"].append(s["difficulty"])
            p["genre"][s.get("genre")] += 1; p["voice"][s.get("voice")] += 1
        for s in songs:  # 表示名は全曲から拾えるように
            self.artist_disp.setdefault(na(s["artist"]), s["artist"])
        self.seen = {key(s["title"], s["artist"]) for s in songs}
        self.ids = {s["id"] for s in songs}
        self.by_key = {key(s["title"], s["artist"]): s["id"] for s in songs}

    def known(self, artist): return na(artist) in self.prof

    def reject_reason(self, title, artist):
        """追加してはいけない理由。None なら追加可。"""
        if not title or not artist: return "空"
        if na(artist) not in self.prof: return "既存アーティスト外"
        if na(title) in self.artist_names: return "入れ替わり"
        if ALT.search(title): return "別バージョン"
        if key(title, artist) in self.seen: return "重複"
        return None

    def add(self, title, artist, year):
        """検証済みの曲を追加して id を返す。"""
        k = na(artist); p = self.prof[k]
        sid = slug(title, artist)
        while sid in self.ids: sid += "-2"
        s = {
            "id": sid, "title": title, "reading": title, "artist": self.artist_disp[k],
            "year": year, "genre": p["genre"].most_common(1)[0][0] or "jpop",
            "voice": p["voice"].most_common(1)[0][0] or "any",
            "energy": round(sum(p["energy"]) / len(p["energy"])) if p["energy"] else 3,
            "difficulty": round(sum(p["difficulty"]) / len(p["difficulty"])) if p["difficulty"] else 3,
            "scenes": [x for x, _ in p["scenes"].most_common(3)] or ["みんなで"],
            "moods": [x for x, _ in p["moods"].most_common(2)] or ["定番"],
            "tags": list(dict.fromkeys([dtag(year), etag(year), GENL.get(p["genre"].most_common(1)[0][0], ""), "最新曲"] + [x for x, _ in p["tags"].most_common(3)])),
            "dam": None, "joysound": None,   # 未確認
        }
        s["tags"] = [t for t in s["tags"] if t]
        self.songs.append(s); self.ids.add(sid)
        self.seen.add(key(title, artist)); self.by_key[key(title, artist)] = sid
        return sid

# ---------------------------------------------------------------- 1) 新曲追記
def update_songs(cat):
    artists = sorted(cat.prof.keys())
    dropped = collections.Counter(); added = 0
    def work(k):
        disp = cat.artist_disp[k]
        out = []
        for r in itunes_artist(disp):
            tn, an, rd = r.get("trackName"), r.get("artistName"), r.get("releaseDate", "")
            if not tn or not an: continue
            if na(an) != k: continue              # 完全一致のみ（巻き込み禁止）
            try: y = int(rd[:4])
            except Exception: continue
            if y < MIN_YEAR: continue
            out.append((tn, an, y, rd))
        out.sort(key=lambda x: x[3], reverse=True)   # 新しい順
        return out
    # 直列（レート制限対策）。約700アーティスト×3.2秒 ≒ 40分。GitHub Actions の月1実行なら問題ない。
    for i, k in enumerate(artists):
        if added >= MAX_NEW_TOTAL: break
        n_art = 0
        for tn, an, y, rd in work(k):
            if added >= MAX_NEW_TOTAL or n_art >= PER_ARTIST_CAP: break
            why = cat.reject_reason(tn, an)
            if why: dropped[why] += 1; continue
            cat.add(tn, an, y); added += 1; n_art += 1
        if i % 100 == 0: print(f"  進捗 {i}/{len(artists)} added={added}", flush=True)
    print(f"songs: added={added} dropped={dict(dropped)} total={len(cat.songs)}")
    return added

# ---------------------------------------------------------------- 2) いま人気TOP100
def update_hot(cat):
    feed = (fetch_json(RSS) or {}).get("feed")
    if not feed or len(feed.get("results", [])) < 50:
        print("hot: 取得失敗（既存 hot.json を維持）"); return 0
    items = []; added = 0; unresolved = 0
    for i, r in enumerate(feed["results"], 1):
        title, artist = r.get("name", ""), r.get("artistName", "")
        k = key(title, artist)
        sid = cat.by_key.get(k)
        if not sid and cat.known(artist) and cat.reject_reason(title, artist) is None:
            y = int((r.get("releaseDate") or str(TODAY))[:4])
            sid = cat.add(title, artist, y); added += 1
        if not sid: unresolved += 1
        items.append({"rank": i, "title": title, "artist": artist, "songId": sid,
                      "releaseDate": r.get("releaseDate"), "url": r.get("url")})
    out = {"updatedAt": TODAY.isoformat(), "source": "Apple Music Japan トップソング（最も再生された曲）",
           "items": items}
    json.dump(out, open(HOT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"hot: {len(items)}曲 解決={len(items)-unresolved} 未収録={unresolved} songs追加={added} updated={feed.get('updated')}")
    return added

def main():
    songs = json.load(open(SONGS, encoding="utf-8"))
    n0 = len(songs)
    cat = Catalog(songs)
    if "--no-songs" not in sys.argv: update_songs(cat)
    if "--no-hot" not in sys.argv: update_hot(cat)
    ids = [s["id"] for s in cat.songs]
    assert len(ids) == len(set(ids)), "id重複"
    assert len(cat.songs) >= n0, "曲数が減った"
    json.dump(cat.songs, open(SONGS, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"added_new={len(cat.songs)-n0} total={len(cat.songs)}")

if __name__ == "__main__":
    main()
