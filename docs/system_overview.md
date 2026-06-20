# System Overview — what this is & why it matters (plain-language guide)

> A friendly explainer for anyone who needs to **understand or present** this project quickly.
> The formal versions are `design3_presentation_spec_EN.md` (the slide build-spec) and
> `business_analysis_EN.md` / `_JA.md` (the business report). **This file is the easy one.**
>
> 🇬🇧 English first · 🇯🇵 日本語はその下にあります。

---

# 🇬🇧 English

## In one sentence
On Google Maps almost **every restaurant is 4.5★**, so the star can't tell you which one is
actually good. We built a **Food Quality Score (FQS)** that reads the reviews and scores **only the
food** — so you can finally tell restaurants apart, and rank them the way **you** care about.

## The problem (with an analogy)
Imagine a class where **everyone scores 95–99** on the exam. The exam is useless for telling who
really understands — it's "saturated." **Google stars are exactly like that.**

In real numbers (we checked **652 Barcelona restaurants**):
- Only **21 of 652** are below 4.0★. **96%** are 4.0★+, **71%** are 4.5★+.
- **12% of all restaurant pairs have the *exact same* star** — the star gives you **no way to
  choose** between them.
- Yet the real food quality underneath is wildly different: in Gràcia, **10 tapas bars all sit at
  4.5★**, but their food score ranges from **−0.10 to +0.95**.

## What the system does (two simple layers)
1. **Layer 1 — Food Quality Score (the new idea).** An AI (Aspect-Based Sentiment Analysis) reads
   every review and **separates "the food" from "the vibe / terrace / service / price."** It scores
   **just the food**. So two 4.5★ places can be **+0.9 vs −0.3** on food — now you can tell them
   apart.
2. **Layer 2 — Personalization.** You slide **what matters to you** (food / service / ambiance /
   price). A *food-first* person and an *ambiance-first* person get **different** top picks — that's
   what makes it a real recommender, not just a re-scoring trick.

## Why it's valuable (who ends up happy)
- **Diners** — stop wasting precious trip meals on tourist traps; discover hidden gems; **choose
  with confidence even when the stars are useless**.
- **Good small restaurants** — get discovered (we found **31 hidden gems** in just 652 venues):
  visibility they can't buy and stars don't grant.
- **The platform (Google)** — protects the **trust that *is* its product**, adds a fresh "Food
  Quality" filter, and surfaces the long tail of local businesses (= more advertisers).
- **The city / tourism board** — can **redistribute visitors** away from saturated traps toward
  genuine local gems (helps over-tourism and the local economy).

## The honest part (this is what makes it credible)
- We had a guess — *"tourist areas review the vibe, not the food."* We **tested it and it was
  WRONG** (food was mentioned 96% in tourist areas *and* 96% in local areas). We **kept it in the
  deck** to prove we actually validated.
- We do **not** claim FQS is "the truth." It **discriminates *differently* from stars.** Proving it
  is "more correct" needs an external expert guide (Repsol/Bib Gourmand) — that's future work.
- We publish **no review text and no author names** (privacy), and we will **never sell ranking
  position** — that would re-create the very bias we remove.

## How to present it (a reading guide to the slide deck `design3`)
The deck tells this story; here's the flow so a presenter just "gets" it:
- **Slides 1–5 — the hook & the opportunity:** "every restaurant is 4.5★, so stars are broken; here's
  who cares and why it's a business."
- **Slide 6 — it's a real 2-layer recommender** (de-bias → personalize), not a re-scorer.
- **Slide 7 — THE proof slide (most important):** show the **two charts** — stars piled at 4.5
  (saturated) vs FQS spread out — and land the line **"12% of restaurants are tied on stars; FQS
  breaks 45% of those ties."**
- **Slides 8–11 — credibility:** where the data came from, the method, personalization in action,
  and the 3-axis evaluation.
- **Slides 12–13 — the money:** business model (no pay-for-rank!) + business impact.
- **Slide 14 — honesty:** the rejected hypothesis + the fairness/legal risks.
- **Slides 15–16 — maturity & the ask:** limits, future work, "pilot in Barcelona."
- **The closing line to memorize:** *"Stars measure popularity. We measure the food. Google should
  ship both."*

## Numbers cheat-sheet (memorize these)
| Say this | Number |
|---|---|
| Data we validated on | **652 restaurants / 3,249 reviews** |
| How saturated stars are | only **21/652** below 4.0★ (96% ≥4.0, 71% ≥4.5) |
| Stars can't choose | **12%** of pairs are tied; FQS separates **45%** of them |
| Same star, different food | 10 Gràcia tapas all 4.5★ → FQS **−0.10 to +0.95** |
| FQS is new info | rank churn Kendall **τ = 0.234** |
| Business yield | **31** hidden gems · **56** tourist traps |
| It's cheap | full AI analysis cost **$0.17** |

## Try it yourself
- **Live app** (real 652 Barcelona restaurants, anonymized): the Streamlit app — switch to *Layer 2*
  and move the **aspect-weight sliders** to watch the ranking change.
- **Code & docs:** https://github.com/HiroakiNakano1985/restaurants_recommender_system

---

# 🇯🇵 日本語

## ひとことで言うと
Googleマップは **どの店もほぼ4.5★** で、星を見ても「結局どこが美味しいの？」が分かりません。そこで
レビューを読んで **料理だけ** を採点する **FQS（Food Quality Score）** を作りました。これで星では
区別できない店を見分けられ、しかも **あなたの重視ポイント** で並べ替えられます。

## 問題（たとえ話で）
**クラス全員がテストで95〜99点**を取る状況を想像してください。点数が天井に張り付いて、誰が本当に
できるのか分かりません＝「飽和」。**Googleの星はまさにこれ**です。

実データ（バルセロナ **652店**）で確認:
- ☆4.0未満は **652店中わずか21店**。**96%** が4.0★以上、**71%** が4.5★以上。
- **全店ペアの12%が“まったく同じ星”** → 星では **どちらを選べばいいか分からない**。
- なのに中身の料理品質は大違い。Gràcia では **タパス10店が全部4.5★**なのに、料理スコアは
  **−0.10〜+0.95** までバラバラ。

## このシステムがやること（シンプルな2層）
1. **第1層 — FQS（新規アイデア）**：AI（アスペクト別感情分析）が全レビューを読み、
   **「料理」と「雰囲気・テラス・サービス・価格」を切り分け**、**料理だけ**を採点。だから同じ4.5★でも
   料理は **+0.9 と −0.3** のように差が出て、ようやく見分けられます。
2. **第2層 — 個別化**：**あなたが重視するもの**（料理／サービス／雰囲気／価格）をスライダーで指定。
   *料理重視の人* と *雰囲気重視の人* で **上位の店が変わる** → ただの再採点ではなく「本物の推薦
   システム」である証拠。

## 何が嬉しいか（誰が幸せになるか）
- **利用者** — 貴重な旅の食事を観光トラップで無駄にしない／隠れた名店を発見／**星が役立たない時でも
  自信を持って選べる**。
- **良い小さな店** — 発掘される（652店中 **31の隠れ名店** を抽出）。お金で買えない・星では得られない
  露出。
- **プラットフォーム（Google）** — **“信頼”という製品価値を守り**、新しい「料理品質」フィルタを追加、
  ローカル店のロングテール（＝広告主）を掘り起こす。
- **都市・観光局** — トラップから本物の地元名店へ **観光客を再分配**（オーバーツーリズム緩和・地域
  経済支援）。

## 誠実なところ（だから信頼できる）
- 仮説 *「観光地のレビューは雰囲気ばかりで料理に触れない」* を立てて **検証 → 外れ**（料理言及は観光
  96%・地元96%で同じ）。**あえてスライドに残し**、ちゃんと検証したことを示します。
- FQSが「正解」だとは **主張しません**。星とは **“別の軸で”識別** しているだけ。「より正しい」と証明する
  には外部の専門ガイド（Repsol/Bib Gourmand）が必要＝今後の課題。
- **レビュー本文も投稿者名も公開しません**（プライバシー）。そして **掲載順位を売りません**（それをやると
  除去したはずのバイアスが復活するため）。

## プレゼンの進め方（スライド `design3` の読み解きガイド）
デッキはこの流れ。担当者が一読で掴めるように:
- **スライド1〜5 — つかみと機会**：「どの店も4.5★＝星は壊れている。誰が困り、なぜビジネスになるか」。
- **スライド6 — これは本物の2層推薦**（de-bias→個別化）であって再採点ではない。
- **スライド7 — 最重要の“証拠”スライド**：**2枚のグラフ**（星は4.5に山／FQSは広がる）を見せ、
  **「12%の店は星が同点。FQSはそのうち45%を区別できる」** を決める。
- **スライド8〜11 — 信頼性**：データの出所、手法、個別化の実演、3軸評価。
- **スライド12〜13 — お金の話**：ビジネスモデル（掲載順位は売らない！）＋事業インパクト。
- **スライド14 — 誠実さ**：棄却した仮説＋公平性・法務リスク。
- **スライド15〜16 — 成熟度と提案**：限界・今後、「バルセロナでパイロット」。
- **締めの一言（暗記推奨）**：*「星は人気を測る。我々は料理を測る。Googleは両方を載せるべきだ。」*

## 数字チートシート（暗記用）
| こう言う | 数字 |
|---|---|
| 検証データ | **652店 / 3,249レビュー** |
| 星の飽和 | ☆4.0未満は **21/652** だけ（96%が4.0★+、71%が4.5★+） |
| 星では選べない | 全ペアの **12%** が同点。FQSはそのうち **45%** を区別 |
| 同じ星でも料理は別 | Gràciaのタパス10店が全部4.5★ → FQS **−0.10〜+0.95** |
| FQSは新情報 | 順位churn Kendall **τ = 0.234** |
| 事業の収穫 | **31** の隠れ名店・**56** の観光トラップ |
| 安い | AI解析の総コスト **$0.17** |

## 触ってみる
- **公開アプリ**（実バルセロナ652店・匿名化）：Streamlitアプリ。*Layer 2* に切り替えて
  **アスペクト重みスライダー**を動かすと推薦順位が変わります。
- **コード・ドキュメント**：https://github.com/HiroakiNakano1985/restaurants_recommender_system
