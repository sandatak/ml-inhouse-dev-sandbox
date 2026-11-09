---
name: "openlogi-shipping-csv"
description: "オープンロジ出荷依頼（ストア販売分）の取り込みCSVを、b-dash配送先回答・管理表の購入データ・突合リストから組み立てる。Use when オープンロジの出荷依頼CSVを作りたい、サイン会などの特典発送CSVを作りたいとき。"
---

# オープンロジ出荷依頼CSV（ストア販売分）

手順の原本：Confluence「オープンロジ発送依頼（ストア販売分）」 https://booklista.atlassian.net/wiki/spaces/RS/pages/3217883158
運用整理・サンプル：Drive フォルダ https://drive.google.com/drive/folders/1M_EcCIJ6M0IHf3UqzFFSDBrP3mFLgEOv
ルール確認（赤荻さん回答・2026-11-04）：https://docs.google.com/document/d/1-4c43Ssswb9viO1YmK2-yZHIaDvcEcta8iS1QJquOV8/edit

このスキルの担当は **④出荷依頼のCSV作成まで**。ポータルへの取り込み・エラー修正・保留設定・Slack連絡は人が行う（最後にリマインドを出す）。
最終ゴール：テストを重ねて常に正確なCSVを出せるようにしたうえで、Claudeを介さず個人情報取り扱いPCだけで動くアプリにする。スクリプトはそのための部品なので、Claude依存の処理を入れない（標準ライブラリのみ・通信なし）。

## 個人情報の扱い（最重要）

配送先CSVには氏名・住所・電話・メール・ニックネームが入る。**Claudeは中身を読まない・会話に出さない。**
- 実データは、ユーザーのPCに接続したフォルダ内で、デバイスのシェル（device_bash）から下のスクリプトを実行して処理する。クラウド作業領域へステージしない。
- Read・cat・head 等で入力CSVや出力CSVを開かない。確認は検算レポートとワーニング（件数・梱包No・注文番号・会員ID先頭8桁・回答IDのみ）だけで行う。
- デバイスのシェルが無いときは、スクリプト（build_opl_csv.py）をファイルで渡し、ユーザーに実行してもらう。
- ダミーデータ（サンプルフォルダの 26xx_test_*）は読んでよい。

## 入力（案件ごと）

| 入力 | 取得元 | 列 |
|---|---|---|
| 配送先回答 | b-dash（データパレット）の「特典配送先登録フォーム」回答をCSVでDL（Shift_JIS） | 回答ID, 顧客ID(空欄), 注文番号, 郵便番号, 都道府県, 住所, 建物名, 姓, 名, 電話番号, メールアドレス… |
| 購入データ | 案件の管理表（例：202610_○○オンラインサイン会_参加者リスト）の「事前購入」＋「追加販売分（ストアバック）」 | AID, No, 注文番号, PDC, RS会員ID |
| 突合リスト（梱包No） | 管理表の「住所登録」シート。**赤荻さんが手動で作る**。1会員＝1梱包No | RS会員ID, 梱包No（例 yymm_CP名_001） |
| 商品情報 | オープンロジの商品マスタ（①で登録済み）＋プラン対応。AIDごとに1行、**優先度の高いプランから順に並べる** | AID, プラン, 商品ID, 商品名, 品名, 緩衝材指定, 緩衝材 |

商品情報の例（行の並び＝優先度＝CSV内での並び順）：
```
AID,プラン,商品ID,商品名,品名,緩衝材指定,緩衝材
LT000255643004776689,A,MB781-I000997,【Aプラン】FOGO特典,ブロマイド、チェキ、アクリルキーホルダー,1,BUBBLE_PACK
LT000255643004776690,B,MB781-I000998,【Bプラン】FOGO more特典,ブロマイド、チェキ,,
```
- アクキー入りプランは「緩衝材指定=1」「緩衝材=BUBBLE_PACK」。
- 商品名はお客様の納品書に出る名称（セットならセット商品ID・セット名）。

## 突合リスト（梱包No）について

- **Claudeは作らない。** 赤荻さんが手動で作成する。
- 梱包Noは納品物（サイン入り商品）の並び順に振られている。バラバラだとオープンロジの入荷検品で手数料が発生するため、CSVも梱包No順に並べる。
- 滑り込みで参加登録〜サイン入れされた人がいると、梱包Noの順は購入順と一致しない。購入順で並べ替えたり番号を振り直したりしない。

## 組み立てルール（Excel作業用ブックのVLOOKUPと同じ）

1. 配送先回答の顧客IDは空欄 → **注文番号で購入データを引いてRS会員IDを補完**。注文番号の末尾の空白は必ずtrimして照合。
2. 購入データに無い注文番号の回答（テスト回答 000000000000 等）は除外。
3. 同じ会員の回答が複数あれば、**回答IDが大きい（新しい）方を採用**し、ワーニングに梱包No・注文番号・回答IDを出す（内容が違えば【要確認】）。
4. 数量（出荷依頼数）＝会員×AIDごとの注文番号の件数。
5. 梱包No（CSVの「注文番号」列）＝突合リストを会員IDで引く。
6. 配送先が未登録の会員は出荷しない → ワーニングの［未発送］。突合リストに梱包Noが無い会員はCSVに入れず［要確認］。
7. 配送先氏名＝姓＋半角スペース＋名。郵便番号・電話番号はハイフン無しの文字列（先頭0を落とさない）。
8. **同梱時の揃え方：その梱包に入っているプランのうち、優先度がいちばん高いプラン（＝その梱包の先頭行）の「緩衝材指定・緩衝材・品名」に、その梱包の全行を揃える。** CSV全体や商品情報の一番上のプランには揃えない。例（Aだけアクキー入り、優先度A→B→C）：B＋C→Bに揃える（緩衝材なし）、A＋C→Aに揃える（1 / BUBBLE_PACK）、Cのみ→Cのまま、A＋B＋C→A。
9. 並び順は梱包No順、同じ梱包内は優先度順（商品情報の行順）。複数商品の同梱は行が増える。
10. 配送便指定：既定 4（佐川）。**ユニーク商材（ニックネーム入り等）が無い案件ではネコポス 2 に変わることがある** → 毎回ユーザーに確認し `--delivery` で指定。
11. 固定値：出荷予約=1、ご依頼主＝1070052 / 東京都 / 港区赤坂2-5-27 / Reader Store、お問い合わせ先=URL、ご依頼主電話番号=0335683372、お問い合わせフォーム=https://ebookstore.sony.jp/mtc/stc/help/support/
12. 出力はオープンロジのテンプレ形式：57列、見出し2行（列名＋【必須】【任意】行）、UTF-8 BOM付き、CRLF。ファイル名は `出荷依頼_yyyymm_CP名_mmdd.csv`。ワーニングは同じ場所に `<CSV名>_ワーニング.txt`。

## 手順

1. ユーザーに案件名・管理表のURL・**配送便（佐川4／ネコポス2）**・ユニーク商材の有無・**プランの優先度順**を確認する。
2. 管理表から購入データ（事前購入＋追加販売分）と突合リストをCSVで、接続フォルダに書き出してもらう。b-dashの配送先CSVもユーザーがDLして同じフォルダへ。
3. 商品情報CSVを作る（AID・商品ID・商品名・品名・緩衝材をユーザーに確認し、優先度の高い順に並べる）。商品情報は個人情報を含まないのでClaudeが書いてよい。
4. 下のスクリプトを接続フォルダ（または作業フォルダ）に置き、デバイスのシェルで実行：
   ```
   python3 build_opl_csv.py --bdash <配送先.csv> --orders <購入データ.csv> --konpo <突合リスト.csv> --plans <商品情報.csv> --delivery 4 --out 出荷依頼_yyyymm_CP名_mmdd.csv
   ```
5. 検算レポートを確認してユーザーに伝える：出力行数・梱包数・数量合計、購入数との差（＝未発送分）、［除外］［重複回答］［未発送］［要確認］の各行。
   - ［要確認］があれば止めて赤荻さんに確認。
   - 購入数合計−出力数量合計が［未発送］の数量合計と一致すること。
   - ワーニングのテキストは赤荻さんにそのまま渡せる（個人情報なし）。
6. 納品時に必ずリマインドを添える（下記）。

## 納品時のリマインド（人の作業）

- CSV取り込みは **9:00と12:30前後を避ける**（即時連携されリカバリ不可）。
- 取り込み後、郵便番号と住所の不一致エラーを確認・修正。
- **ユニーク商材（ニックネーム入り等）を含む場合は取り込み後すぐ「保留」設定**→Slackでオープンロジ担当へ出荷依頼登録と保留設定を連絡（検品後に先方がステータス変更）。
- ユニーク商材突合リスト（②）は鍵付きExcelで事前共有済みか確認（Passはファイル名末尾の日付4桁）。

## スクリプト build_opl_csv.py

```python
"""オープンロジ出荷依頼CSVを組み立てる（ストア販売分）。個人情報は標準出力にもワーニングにも出さない。

入力:
  --bdash  b-dash（データパレット）配送先フォーム回答CSV（Shift_JIS）
  --orders 購入データ（AID, No, 注文番号, PDC, RS会員ID）※事前購入＋追加販売分
  --konpo  突合リスト（RS会員ID, 梱包No）※赤荻さんが手動作成。梱包Noは納品物の並び順
  --plans  商品情報（AID, プラン, 商品ID, 商品名, 品名, 緩衝材指定, 緩衝材）※上の行ほど優先
  --delivery 配送便指定（4=佐川〈既定〉 / 2=ネコポス：ユニーク商材なしの案件で使うことがある）
出力:
  --out    出荷依頼CSV（UTF-8 BOM・CRLF・見出し2行）
  --warn-out ワーニング（テキスト）。省略時は <out>_ワーニング.txt
  標準出力に検算レポート
"""
import argparse, csv, io, os, sys
from collections import OrderedDict, defaultdict

HEADER = "商品ID,商品名,商品コード,軽減税率適用商品,サイズ,在庫数,出荷依頼数,出荷予約,単価,合計金額,小計,配送料,手数料,割引額,総計,総計通常税率,総計軽減税率,配送先郵便番号,配送先都道府県,配送先住所,配送先マンション・ビル名,配送先氏名,配送先会社名,配送先電話番号,配送先連絡メール,配送先マスタ登録,注文番号,配送便指定,配送会社指定,出荷希望日,お届け希望日,希望時間帯,緩衝材指定,緩衝材,ギフトラッピング単位,ラッピングタイプ,贈り主氏名,同梱指定,不在時宅配ボックス,割れ物注意,品名,明細書メッセージ,発送通知メッセージ,明細書の同梱,明細書の金額印字,ご依頼主郵便番号,ご依頼主都道府県,ご依頼主住所,ご依頼主マンション・ビル名,ご依頼主氏名,ご依頼主会社名,ご依頼主部署名,お問い合わせ先,ご依頼主電話番号,ご依頼主メールアドレス,お問い合わせフォーム,ご依頼主UUID".split(",")
NOTE = "【商品ID列か商品コード列のいずれか必須】,【任意】,【商品ID列か商品コード列のいずれか必須】,【任意】,【入力不要】,【入力不要】,【必須】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【必須】,【必須】,【必須】,【任意】,【必須】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【任意】,【ご依頼主UUID未指定時は必須】,【ご依頼主UUID未指定時は必須】,【ご依頼主UUID未指定時は必須】,【任意】,【ご依頼主UUID未指定時は必須】,【任意】,【任意】,【任意】,【ご依頼主UUID未指定時は必須】,【任意】,【任意】,【任意。指定時は他の依頼主項目は無視】".split(",")
SENDER = {"ご依頼主郵便番号": "1070052", "ご依頼主都道府県": "東京都", "ご依頼主住所": "港区赤坂2-5-27",
          "ご依頼主氏名": "Reader Store", "お問い合わせ先": "URL", "ご依頼主電話番号": "0335683372",
          "お問い合わせフォーム": "https://ebookstore.sony.jp/mtc/stc/help/support/"}
ADDR_KEYS = ("郵便番号", "都道府県", "住所", "建物名", "姓", "名", "電話番号", "メールアドレス")


def read_csv(path, enc="utf-8-sig"):
    raw = open(path, "rb").read()
    for e in (enc, "utf-8-sig", "cp932"):
        try:
            return list(csv.DictReader(io.StringIO(raw.decode(e))))
        except UnicodeDecodeError:
            continue
    sys.exit(f"文字コードを判別できません: {path}")


def main():
    ap = argparse.ArgumentParser()
    for k in ("bdash", "orders", "konpo", "plans", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--delivery", default="4", choices=["4", "2"])
    ap.add_argument("--warn-out")
    a = ap.parse_args()
    warn_path = a.warn_out or os.path.splitext(a.out)[0] + "_ワーニング.txt"
    warn = []

    plans = OrderedDict((r["AID"].strip(), r) for r in read_csv(a.plans))
    plan_rank = {aid: i for i, aid in enumerate(plans)}
    orders = read_csv(a.orders)
    order2member = {}
    for r in orders:
        on, m = r["注文番号"].strip(), r["RS会員ID"].strip()
        if on in order2member and order2member[on] != m:
            warn.append(f"[要確認] 注文番号 {on} に複数の会員IDが紐づいている")
        order2member[on] = m
    konpo = {}
    for r in read_csv(a.konpo):
        m, k = r["RS会員ID"].strip(), r["梱包No"].strip()
        if not m:
            continue
        if m in konpo and konpo[m] != k:
            warn.append(f"[要確認] 突合リストで同じ会員に梱包Noが2つ（{konpo[m]} / {k}）")
        konpo[m] = k

    # 配送先：注文番号→会員IDで顧客IDを補完。同じ会員の回答が複数なら回答IDが大きい（新しい）方を採用
    answers = defaultdict(list)
    for r in read_csv(a.bdash, "cp932"):
        on = r["注文番号"].strip()
        m = r.get("顧客ID", "").strip() or order2member.get(on)
        if not m:
            warn.append(f"[除外] 配送先回答 回答ID={r['回答ID']} 注文番号={on}：購入データに無い（テスト回答等）")
            continue
        answers[m].append(r)
    addr = {}
    for m, rs in answers.items():
        rs.sort(key=lambda r: int(r["回答ID"]))
        addr[m] = rs[-1]
        if len(rs) > 1:
            same = all(rs[0][k] == x[k] for x in rs for k in ADDR_KEYS)
            ids = "・".join(r["回答ID"] for r in rs)
            ons = "・".join(sorted({r["注文番号"].strip() for r in rs}))
            warn.append(f"[重複回答] 梱包No={konpo.get(m, '(突合リストに無し)')} 注文番号={ons} 回答ID={ids} → 回答ID {rs[-1]['回答ID']} を採用"
                        + ("（内容は同じ）" if same else "【内容が異なる・要確認】"))

    # 数量：会員×AID で注文番号を数える
    qty = defaultdict(int)
    for r in orders:
        aid = r["AID"].strip()
        if aid not in plans:
            warn.append(f"[要確認] 商品情報に無いAID {aid}（注文番号 {r['注文番号'].strip()}）")
            continue
        qty[(r["RS会員ID"].strip(), aid)] += 1

    lines, no_addr, no_konpo = [], set(), set()
    for (m, aid), n in qty.items():
        if m not in addr:
            no_addr.add(m); continue
        if m not in konpo:
            no_konpo.add(m); continue
        lines.append((konpo[m], plan_rank[aid], m, aid, n))
    lines.sort()

    # 同じ梱包の行は、その梱包に入っているプランのうち優先度がいちばん高いもの（＝その梱包の先頭行）の
    # 緩衝材指定・緩衝材・品名に揃える。CSV全体や商品情報の一番上には揃えない（例：B＋CならB）
    head = {}
    for k, _, _, aid, _ in lines:
        head.setdefault(k, plans[aid])

    out = io.StringIO()
    w = csv.writer(out, lineterminator="\r\n")
    w.writerow(HEADER); w.writerow(NOTE)
    for k, _, m, aid, n in lines:
        p, ad, base = plans[aid], addr[m], head[k]
        row = dict.fromkeys(HEADER, "")
        row.update({"商品ID": p["商品ID"], "商品名": p["商品名"], "出荷依頼数": str(n), "出荷予約": "1",
                    "配送先郵便番号": ad["郵便番号"].strip().replace("-", ""), "配送先都道府県": ad["都道府県"].strip(),
                    "配送先住所": ad["住所"].strip(), "配送先マンション・ビル名": ad["建物名"].strip(),
                    "配送先氏名": f"{ad['姓'].strip()} {ad['名'].strip()}", "配送先電話番号": ad["電話番号"].strip().replace("-", ""),
                    "配送先連絡メール": ad["メールアドレス"].strip(), "注文番号": k, "配送便指定": a.delivery,
                    "緩衝材指定": base["緩衝材指定"].strip(), "緩衝材": base["緩衝材"].strip(), "品名": base["品名"].strip()})
        row.update(SENDER)
        w.writerow([row[h] for h in HEADER])
    open(a.out, "w", encoding="utf-8-sig", newline="").write(out.getvalue())

    for m in sorted(no_addr, key=lambda x: konpo.get(x, "")):
        warn.append(f"[未発送] 配送先未登録 梱包No={konpo.get(m, '(突合リストに無し)')} 会員 {m[:8]}… 数量={sum(v for (mm, _), v in qty.items() if mm == m)}")
    for m in sorted(no_konpo):
        warn.append(f"[要確認] 突合リストに梱包Noが無い 会員 {m[:8]}…（配送先はあり・CSVに入れていない）")

    summary = [f"出力 {len(lines)}行 / 梱包 {len({l[0] for l in lines})}件 / 数量合計 {sum(l[4] for l in lines)} / 配送便指定 {a.delivery}",
               f"購入データの数量合計 {sum(qty.values())}（差分は配送先未登録・突合リスト漏れの分）"]
    open(warn_path, "w", encoding="utf-8-sig", newline="").write("\r\n".join(summary + warn) + "\r\n")
    print("\n".join(summary + warn))
    print(f"ワーニング → {warn_path}")


if __name__ == "__main__":
    main()
```

## テスト履歴

| 日付 | データ | 結果 |
|---|---|---|
| 2026-10-30 | 202610_杉江さんオンラインサイン会_sample（ダミー） | 出荷依頼_202611_sugie_1029.csv と16行・10梱包すべて一致 |
| 2026-11-04 | 同上＋赤荻さん回答の反映（重複回答ワーニングなど） | 再び一致 |
| 2026-11-04 | 3プランのダミー（Aのみアクキー入り、優先度A→B→C） | B＋C→B、A＋C→A、Cのみ→C、A＋B＋C→A に揃うことを確認（赤荻さんの指摘どおり） |

## 次にテストしたいパターン（アプリ化の前に）

- ネコポス（配送便指定2）の案件
- セット商品（セット商品ID）を使う案件
- 同じ会員が同じプランを複数購入（実データで）
- 滑り込み登録で梱包Noが購入順と一致しない案件
- 重複回答で住所が変わっているケース
- 郵便番号と住所が一致しないケース