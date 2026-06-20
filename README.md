# Barcelona Food Quality Score (FQS)

> *Google stars saturate near 4.5 and lose discriminative power; a review-derived
> **Food Quality Score (FQS)** restores the ability to tell good food apart.*

This project builds a recommender-evaluation pipeline for Barcelona restaurants that
extracts a **food-only quality signal** from review text (Aspect-Based Sentiment Analysis)
and compares it against the raw Google star rating.

*(English below, 日本語はその後)*

---

## English

### The idea
On Google Maps almost every restaurant sits at 4.3–4.9 stars. The star scale is **saturated**:
it can no longer separate a genuinely great kitchen from an average one. We compute an **FQS**
from the *food* aspect of each review (ignoring ambiance / service / price), so that two
"identical" 4.5★ restaurants can be ordered by how good the food actually is.

### Pipeline / architecture
```
ingest ─▶ ABSA ─▶ scoring ─▶ rerank ─▶ analysis / eval / app
(grid    (food    (FQS =     (star vs   (figures, metrics,
 fetch    aspect   weighted   FQS rank   Streamlit demo)
 + synth) sentiment) mean)     delta)
```

### What was built (by module)
| Module | Purpose |
|---|---|
| `ingest/schema.py` | `Review` / `Place` dataclasses — keep all metadata, no lossy text flattening |
| `ingest/synth.py` | Synthetic data generator (pipeline validation when real data is unavailable) |
| `ingest/places_grid.py` | Google Places API (New) grid fetch (district × cuisine), JSONL store, cost cache |
| `config/districts.py`, `config/cuisines.py` | 20 Barcelona districts (tourist/local tags) × 10 cuisines |
| `nlp/absa.py` | ABSA: `SimpleAbsa` (offline, reads embedded aspects) + `LlmAbsa` (Gemini, JSON mode, batching, timeout/retry, multilingual) |
| `scoring/fqs.py`, `scoring/weights.py` | FQS = weighted mean of food sentiment (time decay, reviewer weight, cuisine normalization; all ablatable flags) |
| `rerank/reranker.py` | Star-order vs FQS-order within district × cuisine → `rank_delta` (gems / traps) |
| `analysis/divergence_report.py` | Synthetic STEP2–4 figures (scatter, aspect-mention, before/after) |
| `analysis/real_divergence_report.py` | Real-data divergence check (ABSA → FQS → figures), with resume/checkpoint |
| `eval/proxy_labels.py`, `eval/metrics.py`, `eval/run_eval.py` | Proxy-label evaluation (P@K, Recall@K, NDCG, AUC, ablation) — synthetic |
| `eval/divergence_metrics.py` | **In-house metrics on real data** (no external labels): saturation, tie-resolution, choice resolution, hidden gems, traps, rank churn |
| `app/streamlit_app.py`, `app/data_loader.py` | Demo UI: sort-axis toggle, scatter, store cards (explainable), folium map |

### Real-data results (652 Barcelona restaurants, 3,249 reviews)
Fetched 5 districts (tourist: Barceloneta, La Rambla; local: Gràcia, Sant Andreu; mixed: Eixample) × 10 cuisines.

- **Star saturation**: mean 4.54, 96% of stores ≥ 4.0, only **21 stores in the 3.x band**. Stars barely discriminate.
- **Tie-resolution (headline)**: **12%** of all store pairs share the *same* star (indistinguishable). Among them, FQS separates **45%** by |Δ| ≥ 0.2 (69% by ≥ 0.1).
- **Choice resolution**: within a district × cuisine, the average spread is star **0.210** vs FQS **0.408** (normalized). Example — *Gràcia tapas*: 10 stores all at ⭐4.5, FQS from **−0.10 to +0.95**.
- **Business**: 31 hidden gems (star ≤ 4.4 but top-quartile FQS), 56 absolute traps (star ≥ 4.6 but bottom-quartile FQS), rank churn **Kendall τ = 0.234** (FQS is largely new information, not a restatement of stars).
- **Naive divergence**: Pearson(star, FQS) = **0.448** — divergence exists but is moderate; the dominant effect is star *range restriction*, which is exactly the saturation story.

### Honest framing (important)
- The original hypothesis "stars are *wrong* / diverge strongly" and "tourist reviews skip food" did **not** hold on real data (food is mentioned ~96% in both tourist and local areas). We pivoted to the honest, data-supported claim: **stars are saturated and non-discriminative; FQS restores resolution**.
- The in-house metrics show FQS makes a **different** discrimination, **not** that it is **truly more correct**. Final proof needs an external ground truth.
- Michelin labels were attempted but only **4 / 652** matched and were off-target (casual good-food places), so external-label validation was abandoned for now.
- Data limits: at most **5 reviews per store** (Places hard cap); Google returns *relevance-ranked* (positive-leaning) reviews; FQS tops out near +1 where reviews are uniformly rave.

### How to run
```bash
pip install -r requirements.txt

# Synthetic pipeline (no API, no cost)
python -m analysis.divergence_report      # 3 figures to reports/
python -m eval.run_eval                   # proxy-label evaluation + figures
streamlit run app/streamlit_app.py        # demo UI

# Real data (needs keys in .env; INCURS CHARGES)
#   GOOGLE_PLACES_API_KEY=...   GEMINI_API_KEY=...
python -m ingest.places_grid --smoke      # 2-query smoke test first
python -m analysis.real_divergence_report # ABSA + FQS + divergence (resumable)
python -m eval.divergence_metrics         # in-house real-data metrics (re-reads saved ABSA, no charge)
```
Costs incurred so far: Text Search ×52, Place Details (Atmosphere SKU) ×652, Gemini ABSA ≈ \$0.17.

### Known limitation / technical debt
`ingest/synth.py` shares `config/districts.py` and `config/cuisines.py` with the real-data fetch,
so editing those (done when expanding to 20 districts) changes the synthetic distribution. This is
incidental coupling — synth should own fixed `SYNTH_DISTRICTS` / `SYNTH_CUISINES`. Recorded in a
comment block at the top of `synth.py`; left unfixed deliberately (synthetic data has served its
purpose now that the focus is real-data evaluation).

---

## 日本語

### アイデア
Google マップでは飲食店のほとんどが ☆4.3〜4.9 に密集しており、星は**飽和**して「本当に料理が良い店」と
「平凡な店」を区別できません。本プロジェクトは各レビューの *food*（料理）アスペクトだけから **FQS
（Food Quality Score）** を算出し、雰囲気・サービス・価格を剥がした料理品質で、見かけ上同じ ☆4.5 の
店どうしを並べ替えられるようにします。

### パイプライン構成
```
ingest ─▶ ABSA ─▶ scoring ─▶ rerank ─▶ analysis / eval / app
(グリッド  (料理     (FQS=     (星順 vs   (図・指標・
 取得+合成) アスペクト 加重平均)  FQS順の差) Streamlit デモ)
          感情)
```

### 作ったもの（モジュール別）
| モジュール | 役割 |
|---|---|
| `ingest/schema.py` | `Review` / `Place` データクラス（情報を捨てない構造化保存） |
| `ingest/synth.py` | 合成データ生成器（実データが無い時のパイプライン検証用） |
| `ingest/places_grid.py` | Google Places API (New) の地区×ジャンル グリッド取得、JSONL保存、二重課金回避キャッシュ |
| `config/districts.py`, `config/cuisines.py` | バルセロナ20地区（観光/地元タグ）× 10ジャンル |
| `nlp/absa.py` | ABSA: `SimpleAbsa`（オフライン）＋ `LlmAbsa`（Gemini, JSONモード, バッチ, タイムアウト/リトライ, 多言語） |
| `scoring/fqs.py`, `scoring/weights.py` | FQS = 料理感情の加重平均（時間減衰・レビュアー重み・ジャンル正規化、全てフラグでablation可） |
| `rerank/reranker.py` | 同一エリア×ジャンル内の 星順 vs FQS順 → `rank_delta`（発掘優良店/観光トラップ） |
| `analysis/divergence_report.py` | 合成データの STEP2-4 図（散布図・アスペクト言及率・before/after） |
| `analysis/real_divergence_report.py` | 実データ乖離判定（ABSA→FQS→図）、中断再開つき |
| `eval/proxy_labels.py`, `eval/metrics.py`, `eval/run_eval.py` | 代理ラベル評価（P@K, Recall@K, NDCG, AUC, ablation）— 合成 |
| `eval/divergence_metrics.py` | **実データの自前メトリクス**（外部ラベル不要）: 飽和・同点解消・選択可能性・発掘優良店・トラップ・rank churn |
| `app/streamlit_app.py`, `app/data_loader.py` | デモUI: ソート軸トグル・散布図・店舗カード（説明可能）・folium地図 |

### 実データ結果（バルセロナ652店・3,249レビュー）
5地区（観光: Barceloneta, La Rambla／地元: Gràcia, Sant Andreu／混在: Eixample）× 10ジャンルを取得。

- **星の飽和**: 平均4.54、☆4.0以上が96%、**3点台はわずか21店**。星はほとんど区別できていない。
- **同点解消（核心）**: 全ペアの **12%** が星“同値”で区別不能。そのうち FQS が |Δ|≥0.2 で **45%**（≥0.1 で69%）を分離。
- **選択可能性**: 同一エリア×ジャンル内の平均レンジは 星 **0.210** vs FQS **0.408**（正規化）。例 — *Gràcia tapas*: 同じ ☆4.5 の店10軒の FQS が **−0.10〜+0.95**。
- **ビジネス**: 埋もれた良店31店（星≤4.4 だが FQS上位25%）、絶対トラップ56店（星≥4.6 だが FQS下位25%）、rank churn **Kendall τ=0.234**（FQS は星の焼き直しでなく別情報）。
- **素朴な乖離**: Pearson(星, FQS)=**0.448** — 乖離は在るが中程度。主因は星のレンジ制限であり、それ自体が「飽和」の物語。

### 正直なフレーミング（重要）
- 当初仮説「星は**間違い**／強く乖離」「観光地のレビューは料理に触れない」は実データで**成立せず**（food言及は観光・地元とも約96%）。データが支持する形に修正：**星は飽和・非識別／FQS が識別力を回復する**。
- 自前メトリクスが示すのは「FQS は星と**異なる**識別をする」であって「**真に正しい**」ではない。最終証明には外部正解が必要。
- Michelin ラベルを試みたが **652店中4店**マッチ・ターゲットとズレのため断念。
- データ限界: 1店**最大5レビュー**、Google の関連性上位（好意偏り）レビュー、FQS は絶賛偏りで上位が +1 付近に飽和。

### 実行方法
```bash
pip install -r requirements.txt

# 合成パイプライン（API不要・無課金）
python -m analysis.divergence_report      # reports/ に図3枚
python -m eval.run_eval                   # 代理ラベル評価＋図
streamlit run app/streamlit_app.py        # デモUI

# 実データ（.env にキーが必要・課金あり）
#   GOOGLE_PLACES_API_KEY=...   GEMINI_API_KEY=...
python -m ingest.places_grid --smoke      # まず2クエリのスモークテスト
python -m analysis.real_divergence_report # ABSA＋FQS＋乖離（再開可能）
python -m eval.divergence_metrics         # 実データ自前メトリクス（保存済みABSAを再利用・無課金）
```
これまでの実課金: Text Search ×52、Place Details（Atmosphere SKU）×652、Gemini ABSA ≈ \$0.17。

### 既知の限界 / 技術的負債
`ingest/synth.py` が実取得用の `config/districts.py` / `config/cuisines.py` を共有しており、これらを編集
（20地区拡張時）すると合成分布が変わります。これは不要な結合で、本来 synth は専用の固定リスト
（`SYNTH_DISTRICTS` / `SYNTH_CUISINES`）を持つべきです。`synth.py` 冒頭のコメントに記録済み。主軸が
実データ評価に移ったため、意図的に未修正としています。

---

> Note: the canonical design specs in `docs/` (`design1_validation_blueprint.md`,
> `design2_system_blueprint.md`, `design3_presentation_spec_EN.md`) remain in their original
> language and are intentionally not modified by this translation pass.
