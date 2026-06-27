#!/usr/bin/env python3
"""
カラオケ選曲ナビ — 月次「最新曲」追記スクリプト。
既存 songs.json のアーティストについて iTunes で直近の新曲だけを取得し、
重複を除いて追記する（ベースの手作り曲は保持）。GitHub Actions から月1で実行。

- 出所: iTunes Search API（曲名・歌手名は事実情報）。新曲のみ・控えめに追記。
- ジャンル/声域は既存DBのアーティスト属性を継承（誤分類を防ぐ）。
"""
import json, re, sys, time, urllib.parse, urllib.request, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = __file__.rsplit("/", 1)[0] if "/" in __file__ else "."
PATH = HERE + "/songs.json"
THIS_YEAR = datetime.date.today().year
MIN_YEAR = THIS_YEAR - 1          # 直近2年（昨年〜今年）の新曲のみ追記
MAX_NEW_TOTAL = 1200              # 1回の追記上限（控えめに）
PER_ARTIST_CAP = 8               # 1アーティストの新曲上限
UA = "Mozilla/5.0"

NOISE = re.compile(r"カラオケ|karaoke|\binstrumental\b|インストゥルメンタル|オルゴール|オフボーカル|off vocal|\bbgm\b|作業用|inst\.|cover|カバー|remix|リミックス|\blive\b|ライヴ|ライブ", re.I)
GENL = {"jpop":"邦楽","anime":"アニソン","vocaloid":"ボカロ","band":"バンド","western":"洋楽","kpop":"K-POP","chinese":"華語","enka":"演歌・昭和"}

def na(a): a=a.lower(); a=re.split(r"feat|／|/| x |×|（|\(",a)[0]; return re.sub(r"\s+","",a)
def nt(t): t=re.sub(r"[（(].*?[)）]","",t); return re.sub(r"[\s・〜~,.!?’'\-]","",t.lower())
def key(s): return nt(s["title"])+"|"+na(s["artist"])
def dtag(y): return "〜60年代前" if y<1960 else (f"{(y//10)*10}年代" if y>=2000 else f"{(y//10)*10%100}年代")
def etag(y): return "令和" if y>=2019 else ("平成" if y>=1989 else "昭和")
def slug(t,a): return (re.sub(r"[^a-z0-9]+","-", (t+"-"+a).lower()).strip("-")[:40]) or "song"

def itunes(artist):
    url = ("https://itunes.apple.com/search?term=" + urllib.parse.quote(artist) +
           "&country=JP&media=music&entity=song&attribute=artistTerm&limit=200")
    for k in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=20) as r:
                return json.load(r).get("results", [])
        except Exception:
            time.sleep(1 + k)
    return []

def main():
    songs = json.load(open(PATH, encoding="utf-8"))
    seen = {key(s) for s in songs}
    ids = {s["id"] for s in songs}
    # アーティスト -> (genre, voice) 属性マップ
    amap = {}
    for s in songs:
        a = s["artist"].split(" feat")[0].split("／")[0].split("×")[0].strip()
        amap.setdefault(a, (s["genre"], s["voice"]))
    artists = list(amap.keys())

    def work(a):
        g, v = amap[a]
        out = []
        for r in itunes(a):
            tn = r.get("trackName"); an = r.get("artistName"); rd = r.get("releaseDate", "")
            if not tn or not an or NOISE.search(tn): continue
            try: y = int(rd[:4])
            except: continue
            if y < MIN_YEAR: continue
            out.append({"title": tn, "artist": an, "year": y, "genre": g, "voice": v})
        out.sort(key=lambda h: len(h["title"]))
        return out[:PER_ARTIST_CAP]

    added = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        for fut in as_completed([ex.submit(work, a) for a in artists]):
            for h in fut.result():
                if added >= MAX_NEW_TOTAL: break
                k = key(h)
                if k in seen: continue
                seen.add(k)
                y = h["year"]
                sid = slug(h["title"], h["artist"])
                while sid in ids:
                    sid += "-2"
                ids.add(sid)
                songs.append({
                    "id": sid, "title": h["title"], "reading": h["title"], "artist": h["artist"],
                    "year": y, "genre": h["genre"], "voice": h["voice"], "energy": 3, "difficulty": 3,
                    "scenes": [], "moods": [], "tags": [dtag(y), etag(y), GENL.get(h["genre"], "")],
                    "dam": True, "joysound": True,
                })
                added += 1

    json.dump(songs, open(PATH, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"added_new={added} total={len(songs)}")

if __name__ == "__main__":
    main()
