# utanavi-data

iOSアプリ「カラオケ選曲ナビ」の曲データ配信リポジトリ。

- `songs.json` … アプリが起動時に取得する曲データ（raw URLを直接読む）。
  - 配信URL: `https://raw.githubusercontent.com/jamstyle2007-dev/utanavi-data/main/songs.json`
  - アプリはこれをキャッシュし、**次回起動から反映**。取得失敗時はアプリ同梱版にフォールバック（オフラインOK）。
- `hot.json` … 「いま人気TOP100」（Apple Music Japan トップソング）。songs.json の実曲に解決済み（`songId`）。
  - 配信URL: `https://raw.githubusercontent.com/jamstyle2007-dev/utanavi-data/main/hot.json`
- `update_songs.py` … 月次更新。既存アーティストの**直近の新曲だけ**を検証付きで追記し、hot.json を作り直す。
- `clean_songs.py` … 2026-08-22 の洗い直しに使った一回限りのスクリプト（記録用）。
- `.github/workflows/monthly-update.yml` … 毎月1日 00:30 JST に自動実行（手動実行も可）。変更があれば自動でcommit/push。

## 品質ルール（2026-08-22 監査で確定）
- アーティスト名は正規化して**完全一致**したものだけ採用（検索の巻き込み禁止）
- 曲名が既存アーティスト名と一致する行（入れ替わり）、feat./remix/TVサイズ/live 等の別バージョン、重複は捨てる
- 場面/ムード/エネルギー/難易度/ジャンル/声域は、そのアーティストの手作り曲から継承（空で入れない）
- DAM/JOYSOUND は確認できないので `null`（アプリでは「未確認」表示）。確認なしに true にしない
- 1アーティスト最大5曲／1回最大300曲

## 手動で更新する
```
python3 update_songs.py            # songs.json に新曲を追記 + hot.json を更新
python3 update_songs.py --no-songs # hot.json だけ
git add songs.json hot.json && git commit -m "update" && git push
```

## 注意
- `songs.json` の件数が4000未満／JSON破損／場面なしの新曲混入は CI が弾く（壊れたデータを全ユーザーへ配らない）。
- 曲名・歌手名は事実情報。新曲のみ控えめに追記する方針。
