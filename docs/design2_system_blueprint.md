# 設計図2: 実装システム設計図（VSCode向け）

> 目的：VSCodeでそのまま実装に着手できる粒度のシステム設計。
> 方針：既存 `mindful-tourism-group-E` の構成（requests + FieldMask + dotenv + Streamlit）を踏襲しつつ、
> **「情報を捨てない構造化保存」「地区×ジャンルのグリッド取得」「ABSA→FQS算出」「再ランキング」「Streamlitデモ」** を新規に積む。
> 既存コードの致命的問題＝`_review_to_text()` がレビューを1本の文字列に潰しメタを破棄している点。**ここを廃し、dict構造のままJSONLで保存する**のが最大の変更。

---

## 0. 全体アーキテクチャ

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ A. Ingest     │ → │ B. ABSA       │ → │ C. Scoring    │ → │ D. Rerank     │
│ (生データ取得)│   │ (アスペクト   │   │ (FQS算出)     │   │ (再ランキング)│
│               │   │  別感情分析)  │   │               │   │               │
└──────────────┘   └──────────────┘   └──────────────┘   └──────┬───────┘
        │                                                          │
        │                  ┌──────────────┐   ┌──────────────┐    │
        └─ fallback ─────→ │ A-sim. 合成   │   │ E. Streamlit  │ ←─┘
                           │ データ生成器  │   │ (デモUI)      │
                           └──────────────┘   └──────┬───────┘
                                                      │
                                       ┌──────────────┴───────┐
                                       │ F. Eval (評価・検証)  │
                                       └──────────────────────┘
```

---

## 1. ディレクトリ構成（新規）

```
bcn-food-quality/
├── .env                          # APIキー（gitignore）
├── .env.example
├── requirements.txt
├── README.md
│
├── config/
│   ├── districts.py              # バルセロナ地区リスト（観光/地元タグ付き）
│   └── cuisines.py               # 料理ジャンルリスト
│
├── ingest/
│   ├── places_grid.py            # ★Module A: 地区×ジャンルのグリッド取得
│   ├── schema.py                 # レビュー/店舗の構造化スキーマ定義
│   └── synth.py                  # ★Module A-sim: 合成データ生成器
│
├── nlp/
│   ├── absa.py                   # ★Module B: アスペクト別感情分析
│   └── reviewer_profile.py       # レビュアー信頼度（McAuley用）
│
├── scoring/
│   ├── fqs.py                    # ★Module C: Food Quality Score算出
│   └── weights.py                # 信号の重み（time decay等）
│
├── rerank/
│   └── reranker.py               # ★Module D: 再ランキング + rank delta
│
├── eval/
│   ├── proxy_labels.py           # Michelin/Repsol掲載リスト読み込み
│   └── metrics.py                # Precision@K, NDCG, AUC, ablation
│
├── app/
│   └── streamlit_app.py          # ★Module E: デモUI
│
├── analysis/
│   └── divergence_report.py      # 設計図1のSTEP2-4を自動描画
│
└── data/
    ├── raw/                      # 取得した生レビュー（JSONL）
    ├── processed/                # ABSA付与済み（Parquet）
    └── labels/                   # 代理正解ラベル（CSV）
```

---

## 2. データスキーマ（最重要：情報を捨てない）

### 2-A. レビュー（`Review`）
```python
# ingest/schema.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Review:
    place_id: str
    review_id: str
    rating: int                      # 1-5（per-review。文字列に埋めない！）
    text: str
    lang: Optional[str] = None       # 言語判定結果
    author_name: Optional[str] = None
    author_id: Optional[str] = None  # Placesでは取れない。McAuleyでは取れる
    publish_time: Optional[str] = None      # ISO（取れれば）
    relative_time: Optional[str] = None     # "2か月前"等（Places Newはこれ）
    has_photo: bool = False
    photo_count: int = 0
    # ↓ ABSA後に付与
    aspect_food: Optional[float] = None      # -1〜+1, 未言及はNone
    aspect_service: Optional[float] = None
    aspect_ambiance: Optional[float] = None
    aspect_price: Optional[float] = None
```

### 2-B. 店舗（`Place`）
```python
@dataclass
class Place:
    place_id: str
    name: str
    star_rating: float               # Google集計星
    review_count: int
    cuisine: Optional[str] = None    # ジャンル（primaryType等）
    price_level: Optional[str] = None
    lat: float = 0.0
    lng: float = 0.0
    district: Optional[str] = None   # 地区（観光/地元判定に使う）
    is_tourist_area: Optional[bool] = None
    # ↓ 算出後に付与
    fqs: Optional[float] = None      # Food Quality Score
    fqs_rank: Optional[int] = None
    star_rank: Optional[int] = None
    rank_delta: Optional[int] = None # star_rank - fqs_rank
```

> **既存コードからの変更点**：`_review_to_text()` を完全削除。`page_content`に文字列を詰めるのではなく、上記dataclassをJSONLで1行1レビューとして保存。ChromaDBは「テキスト検索」が必要な段（Streamlitの自然言語検索）でのみ使い、**スコア算出には構造化データを使う**。

---

## 3. Module A: グリッド取得（`ingest/places_grid.py`）

### 設計意図
既存の `"best restaurants in {city}"` クエリは**分布の頭しか取れない**（＝既に星が高い人気店だけ）。
本提案の核心は「☆4.6のハズレ店」と「☆3点台の良店」の**乖離**なので、**分布の裾を拾う**グリッド検索に変える。

### 仕様
```python
# config/districts.py
DISTRICTS = [
    {"name": "La Rambla",   "tourist": True},
    {"name": "Barceloneta", "tourist": True},
    {"name": "Gothic Quarter", "tourist": True},
    {"name": "Gràcia",      "tourist": False},
    {"name": "Sant Andreu", "tourist": False},
    {"name": "Sants",       "tourist": False},
    {"name": "Eixample",    "tourist": None},  # 混在
    # … 20地区程度
]

# config/cuisines.py
CUISINES = ["tapas", "japanese", "italian", "catalan", "seafood",
            "vegetarian", "burger", "ramen", "paella", "brunch"]
```

```python
# ingest/places_grid.py 主要ロジック
def build_queries():
    # 地区 × ジャンル のグリッド（20 × 10 = 200クエリ）
    for d in DISTRICTS:
        for c in CUISINES:
            yield f"{c} restaurant in {d['name']}, Barcelona", d

def fetch_grid(limit_per_query=20):
    seen = set()  # place_idで重複除去
    for query, district in build_queries():
        places = text_search(query, page_size=20, max_pages=3)  # 60件上限まで
        for p in places:
            if p["id"] in seen:
                continue
            seen.add(p["id"])
            reviews = get_place_reviews(p["id"])   # 最大5件
            save_jsonl(p, reviews, district)        # 構造化保存
```

### FieldMask（課金SKUを意識）
```python
# Text Search: 安いフィールドに絞る
FIELDS_SEARCH = "places.id,places.displayName,places.rating,places.userRatingCount,places.priceLevel,places.location,places.primaryType,places.formattedAddress"

# Place Details: reviewsはAtmosphere SKU（最高額）。必要最小限に
FIELDS_DETAILS = "id,rating,reviews"
```

### ページネーション
既存コードは1ページ（20件）で止まっている。`nextPageToken` で**最大60件**まで取得するループを追加。

### コスト見積（参考）
- Text Search 200回 + Place Details 800回（Atmosphere SKU）≈ 数十ドル規模。
- ⚠️ $200無料クレジットは2026年に廃止された可能性。実行前にGoogle Cloud Consoleで現行料金を必ず確認。

---

## 4. Module A-sim: 合成データ生成器（`ingest/synth.py`）

### 設計意図
実データ取得前でも設計図1の全分析を回せるよう、**バルセロナの実態を反映した合成データ**を生成。
教授の課題は「仮データ可」なので正当。**生成の前提を明示**するのが誠実さのポイント。

### 生成モデル（仮説を埋め込む）

> **改訂 2026-06-20**：下記が現行式（`ingest/synth.py` 実装と一致）。当初式からの変更理由は直後の囲みを参照。

```python
# 各店に「真の料理品質」latent変数を持たせ、星は雰囲気主導で膨らむものとする
true_food_quality ~ Beta(2,2)            # 0-1の潜在的な料理の良さ（FQSの真値軸）
is_tourist_area    ~ Bernoulli(p=地区依存)
ambiance           = 観光: Uniform(0.3, 1.0) / 地元: Uniform(0.0, 0.35)  # 料理以外の魅力（テラス/写真映え）

appeal      = 0.35*true_food_quality + 0.65*ambiance   # 星は雰囲気が支配する
star_rating = clip( 3.4 + 1.7*appeal + noise , 3.0, 5.0 )  # Google実態の膨張帯 ~3.4-4.9

# レビュー本文も生成：観光地ほど food言及率が低く、ambiance/price言及が多い
food_mention_prob = 0.7 - 0.4*is_tourist_area
```

これにより、**設計上「星と料理品質が乖離する」データ**が作られる → 分析で必ず乖離が検出できる。
星が雰囲気主導で膨らむため、**「☆4.6 なのに料理はダメ」な観光トラップ店**が実際に生成される。

> **当初式からの改訂理由**：当初は
> `ambiance_boost = is_tourist * Uniform(0,0.8)` / `star = clip(1 + 4*(0.5*tfq + 0.5*ambiance_boost) + noise, 1, 5)`
> だったが、星が平均~2.4の中央寄り分布になり、(a) Google の膨張した星分布（実店舗は概ね3.5以上）と乖離、
> (b) 食事が星の50%を占めるため「☆4.6のハズレ店」が**原理的に作れず**、設計図1 STEP2/3 の閾値（☆4.0/4.5）で
> 該当が0件になっていた。プロジェクト前提「☆4.6のハズレ店」と設計図1の図に整合させるため、星を現実域へ膨張させ、
> 雰囲気の寄与（0.65）を食事（0.35）より大きくした。

（注：「乖離するように作ったデータで乖離を示す」のは循環論法なので、スライドでは**「実データなら同じパイプラインで検証する」**と明記し、合成はあくまでパイプライン動作デモと位置づける）

---

## 5. Module B: ABSA（`nlp/absa.py`）

### 選択肢（精度 vs 手軽さ）
| 手法 | 長所 | 短所 | 推奨度 |
|---|---|---|---|
| **LLM (Gemini/GPT) でアスペクト抽出** | 多言語に強い・実装速い・既存資産流用 | APIコスト・再現性 | ★本命（既存でGemini使用実績あり） |
| 専用ABSAモデル（PyABSA, SemEval系） | オフライン・再現性 | 多言語/カタルーニャ語に弱い | 次点 |
| 辞書+ルール | 軽量 | 精度低い | デモのみ |

### LLMアプローチ仕様
```python
# nlp/absa.py
PROMPT = """
Analyze this restaurant review. For each aspect, return sentiment in [-1, 1],
or null if the aspect is not mentioned. Return JSON only.
Aspects: food, service, ambiance, price.
Review: {text}
"""
# 出力例: {"food": 0.8, "service": null, "ambiance": -0.2, "price": 0.5}
```
- バッチ処理 + JSONモードで安定化（既存の Gemini JSON mode 実績を流用）。
- `food` が null のレビューは「料理無言及」としてSTEP3の集計に使う。

---

## 6. Module C: FQS算出（`scoring/fqs.py`）

```python
def compute_fqs(place_reviews, weights):
    """店舗のFood Quality Scoreを算出"""
    contribs = []
    for r in place_reviews:
        if r.aspect_food is None:       # 料理無言及は除外
            continue
        w = 1.0
        w *= time_decay(r.publish_time, weights.half_life_days)   # ③時間減衰
        w *= reviewer_weight(r.author_id, weights)                # ②信頼度（McAuleyのみ）
        contribs.append((r.aspect_food, w))
    if not contribs:
        return None                     # 料理言及ゼロの店
    fqs_raw = weighted_mean(contribs)
    return normalize_by_cuisine(fqs_raw, place.cuisine)           # ④ジャンル正規化
```

### 重み設計（`scoring/weights.py`）
```python
@dataclass
class Weights:
    half_life_days: int = 365        # ③ 1年で重み半減
    use_reviewer_weight: bool = False # ② McAuley時のみTrue
    reviewer_food_focus_boost: float = 1.5
```

> ablation（評価）のため、各重みを**フラグでON/OFF**できる設計にしておく。

---

## 7. Module D: 再ランキング（`rerank/reranker.py`）

```python
def rerank(places, scope="district_cuisine"):
    """同一エリア・同一ジャンル内でstar順とFQS順を比較"""
    for group in group_by(places, scope):
        rank_by_star = sorted(group, key=lambda p: -p.star_rating)
        rank_by_fqs  = sorted(group, key=lambda p: -(p.fqs or 0))
        for p in group:
            p.star_rank = rank_by_star.index(p) + 1
            p.fqs_rank  = rank_by_fqs.index(p) + 1
            p.rank_delta = p.star_rank - p.fqs_rank
    # rank_delta > 0 : 星では低いがFQSで上昇 = 発掘優良店
    # rank_delta < 0 : 星では高いがFQSで下落 = 観光トラップ店
```

---

## 8. Module E: Streamlit デモUI（`app/streamlit_app.py`）

### 画面構成（既存のStreamlit資産を流用）
```
┌─────────────────────────────────────────┐
│ サイドバー                                │
│  - 地区選択 / ジャンル選択                │
│  - ソート軸: [Google星] [Food Quality]   │ ← トグルがデモの肝
│  - 重みスライダー（time decay等）         │
├─────────────────────────────────────────┤
│ メイン                                    │
│  [散布図] 星 vs FQS（設計図1 図1）        │
│  [店舗カード]                             │
│    店名 / ⭐4.6 / 🍽FQS 2.8 / ↓トラップ   │
│    "このレビューの80%はテラスとビール"    │
│  [地図] 観光トラップ店を赤、優良店を緑    │
└─────────────────────────────────────────┘
```
- **「同じエリアを星で見るか、料理品質で見るか」をトグルで切り替える**のが最も刺さるデモ。
- 各店に「なぜこのFQSか」の説明（food言及率、代表レビュー抜粋）＝説明可能性。

---

## 9. Module F: 評価（`eval/metrics.py`）

設計図1 §3 を実装。
```python
def evaluate(places, proxy_label_set):
    """専門ガイド掲載店を正解として、星 vs FQS のランキング品質を比較"""
    y_true = [p.place_id in proxy_label_set for p in places]
    results = {}
    for scorer_name, score in [("star", "star_rating"), ("fqs", "fqs")]:
        ranked = sorted(places, key=lambda p: -getattr(p, score))
        results[scorer_name] = {
            "precision@10": precision_at_k(ranked, proxy_label_set, 10),
            "ndcg@10":      ndcg_at_k(ranked, y_true, 10),
            "auc":          roc_auc(getattr_list(places, score), y_true),
        }
    return results   # star と fqs を並べて比較
```
- ablation：`Weights` のフラグを切り替えて `evaluate` を繰り返し、各信号の寄与を表化。

---

## 10. requirements.txt（追加分）
```
requests
python-dotenv
pandas
pyarrow            # Parquet
numpy
scikit-learn       # metrics
scipy              # 相関
matplotlib
streamlit
folium
streamlit-folium
google-generativeai   # ABSA（Gemini）
langdetect            # 言語判定
# chromadb / langchain は自然言語検索を入れる場合のみ
```

---

## 11. 実装順序（おすすめ）

1. **schema.py + synth.py** … 合成データで全体を先に通す（実データ待ちにしない）
2. **absa.py（LLM版）** … 合成テキストにアスペクトを付与
3. **fqs.py + reranker.py** … スコアと再ランキング
4. **divergence_report.py** … 設計図1の図1-3を自動生成 ← ここで初成果
5. **metrics.py** … 評価（合成では代理ラベルも合成）
6. **streamlit_app.py** … デモUI
7. **places_grid.py** … 実データ取得（APIキー入手後）→ 同じパイプラインに流す
8. 実データで 4-5 を再実行 → 本番の図表に差し替え

> ポイント：**1-6を合成データで完成させておけば、実データ（7）が来た瞬間に図表が本物に置き換わる**。実データ取得の有無がボトルネックにならない設計。

---

## 12. 既存コードからの移行メモ

| 既存（mindful-tourism） | 本プロジェクト | 変更理由 |
|---|---|---|
| `_review_to_text()` 文字列連結 | `Review` dataclass + JSONL | メタ情報を捨てない |
| `"best restaurants"` 単一クエリ | 地区×ジャンル グリッド | 分布の裾を拾う |
| 1ページ20件で停止 | nextPageToken で60件 | 取得数確保 |
| ChromaDBにスコア依存 | 構造化データでスコア、Chromaは検索のみ | 数値計算の正確性 |
| カテゴリ=restaurant一括 | primaryType でジャンル細分化 | ④正規化のため |
