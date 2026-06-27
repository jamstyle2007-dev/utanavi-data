# utanavi-data

iOSアプリ「カラオケ選曲ナビ」の曲データ配信リポジトリ。

- `songs.json` … アプリが起動時に取得する曲データ（raw URLを直接読む）。
  - 配信URL: `https://raw.githubusercontent.com/jamstyle2007-dev/utanavi-data/main/songs.json`
  - アプリはこれをキャッシュし、**次回起動から反映**。取得失敗時はアプリ同梱版にフォールバック（オフラインOK）。
- `update_songs.py` … 既存アーティストの**直近の新曲だけ**をiTunesから取得して追記するスクリプト。
- `.github/workflows/monthly-update.yml` … 毎月1日に自動実行（手動実行も可）。新曲があれば自動でcommit/push。

## 手動で更新する
```
python3 update_songs.py     # songs.json に最新曲を追記
git add songs.json && git commit -m "update" && git push
```

## 注意
- `songs.json` の件数が3000未満になる/JSON破損はCIが弾く（壊れたデータを全ユーザーへ配らない）。
- 曲名・歌手名は事実情報。新曲のみ控えめに追記する方針。
