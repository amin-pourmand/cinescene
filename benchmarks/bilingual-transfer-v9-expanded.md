# CineScene Broad Diagnostic

Completed **32/32 HTTP inputs** against `rrf-v9-bilingual-evidence-first`. Engine unchanged: **True**. Technical errors: **0**.

The engine policy is fixed during this run. Cases may have informed earlier development; this is a manual diagnostic sample, not a population accuracy estimate. All retrieval targets were checked by exact catalog ID before execution. Only the intended title is labeled; other plausible adaptations or related stories were not exhaustively judged. Source-informed episode checks, when present, are acceptance checks, not independent scene-recognition evidence.

Publication privacy: non-allowlisted local result labels/IDs are pseudonymized. Rankings and metrics are unchanged; original identities remain in the local checkpoint on E.

Fresh manual bilingual paraphrases, frozen before running v8. Target titles are disjoint from the broad diagnostic's 60 paired topics, not necessarily from every historic experiment. Intended-target labels are not exhaustive relevance judgments. No model training uses these cases.

## Retrieval

| Group | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| All retrieval inputs | 32 | 26 | 81.2% | 30 | 93.8% |
| Manual inputs only | 32 | 26 | 81.2% | 30 | 93.8% |
| en | 16 | 13 | 81.2% | 15 | 93.8% |
| fa | 16 | 13 | 81.2% | 15 | 93.8% |
| mixed | 0 | 0 | n/a | 0 | n/a |

Category and language groups overlap; do not add their counts together.

Persian first-choice concentration: **Gravity** appears first in **1/16** queries. This is a diagnostic symptom, not proof of a single cause; no title-specific correction was applied.

| Category | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| movie_plot | 24 | 22 | 91.7% | 24 | 100.0% |
| series_plot | 8 | 4 | 50.0% | 6 | 75.0% |

## Paired Language Check

The same 16 target stories were described in English and Persian. This is a stronger language comparison than comparing unrelated language samples.

| Language | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| en | 16 | 13 | 81.2% | 15 | 93.8% |
| fa | 16 | 13 | 81.2% | 15 | 93.8% |

Both first: **13**. English-only first: **0**. Persian-only first: **0**. Neither first: **3**.

## Coverage Check

Requested titles/versions, when present, deliberately probe coverage, including known weak areas. They are not a random sample of cinema. Movie remakes require the requested year. Series provider years are not treated as canonical premiere years. Aliases such as La Casa de Papel are resolved exactly.

| Requested title | Requested year | In catalog | Rank | Returned results despite absence |
| --- | --- | --- | --- | --- |

## Non-Retrieval Probes

Negative inputs should produce no movie suggestion or a clear input rejection. Ambiguous-probe passes mean only that the API returned multiple distinct suggestions, not that those suggestions were judged relevant. Invalid inputs must return HTTP 422.

| Kind | Inputs | Passed |
| --- | --- | --- |
| negative | 0 | 0 |
| ambiguous | 0 | 0 |
| invalid | 0 | 0 |

## Complete Input Ledger

Rank `not found` means absent from the ten returned results, not absent from the catalog. The full JSON retains all ten result identities. No private paths, transcripts or plot text are exported.

### retrieval

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| pair-001-en | en | debris destroys their spacecraft and a stranded astronaut must move between stations while running out of oxygen | Gravity | 200 | 1 | Gravity |
| pair-001-fa | fa | آوار فضایی سفینه رو نابود میکنه و فضانوردی که تنها مونده باید قبل از تموم شدن اکسیژن خودش رو از یه ایستگاه به یکی دیگه برسونه | Gravity | 200 | 1 | Gravity |
| pair-002-en | en | joy and sadness get lost inside a girl's mind while her other emotions struggle to handle her family's move to another city | Inside Out | 200 | 1 | Inside Out |
| pair-002-fa | fa | شادی و غم تو ذهن یه دختر گم میشن و احساسات دیگه اش نمیتونن با اسباب کشی خانواده به یه شهر تازه کنار بیان | Inside Out | 200 | 1 | Inside Out |
| pair-003-en | en | two rival stage magicians become obsessed with discovering each other's secret for making a man disappear and reappear | The Prestige | 200 | 1 | The Prestige |
| pair-003-fa | fa | دو شعبده باز رقیب وسواس پیدا میکنن که بفهمن اون یکی چطوری یه آدم رو غیب میکنه و جای دیگه ظاهرش میکنه | The Prestige | 200 | 1 | The Prestige |
| pair-004-en | en | a soldier repeatedly wakes up in another man's body on a train with only a few minutes to identify a bomber | Source Code | 200 | 1 | Source Code |
| pair-004-fa | fa | یه سرباز هی تو بدن یه مرد دیگه داخل قطار بیدار میشه و فقط چند دقیقه وقت داره کسی که بمب گذاشته رو پیدا کنه | Source Code | 200 | 1 | Source Code |
| pair-005-en | en | fishermen rescue a man with bullets in his back who cannot remember his name but discovers he has extraordinary combat skills | The Bourne Identity | 200 | 1 | The Bourne Identity |
| pair-005-fa | fa | ماهیگیرها مردی رو از آب نجات میدن که تو پشتش گلوله خورده و اسمش یادش نیست ولی میفهمه مهارت عجیبی تو مبارزه داره | The Bourne Identity | 200 | 1 | The Bourne Identity |
| pair-006-en | en | a marshal investigates a missing patient at an island psychiatric hospital and begins doubting his own identity | Shutter Island | 200 | 1 | Shutter Island |
| pair-006-fa | fa | یه مامور برای پیدا کردن بیمار گمشده به تیمارستانی تو یه جزیره میره و کم کم به هویت خودش شک میکنه | Shutter Island | 200 | 1 | Shutter Island |
| pair-007-en | en | in a future where people can no longer have children a man must escort a pregnant woman to safety | Children of Men | 200 | 1 | Children of Men |
| pair-007-fa | fa | تو آینده ای که آدمها دیگه نمیتونن بچه دار بشن یه مرد باید زنی رو که حامله شده به جای امن برسونه | Children of Men | 200 | 1 | Children of Men |
| pair-008-en | en | a cynical television weatherman keeps waking up on the same morning in a small town regardless of what he did the day before | Groundhog Day | 200 | 1 | Groundhog Day |
| pair-008-fa | fa | یه هواشناس تلویزیون هر کاری هم بکنه صبح دوباره تو همون روز و همون شهر کوچیک بیدار میشه | Groundhog Day | 200 | 1 | Groundhog Day |
| pair-009-en | en | a programmer visits his boss's isolated home to evaluate a humanoid robot and starts questioning who is manipulating whom | Ex Machina | 200 | 1 | Ex Machina |
| pair-009-fa | fa | یه برنامه نویس میره خونه دورافتاده رئیسش تا یه ربات انسان نما رو آزمایش کنه ولی معلوم نیست واقعا کی داره کی رو بازی میده | Ex Machina | 200 | 1 | Ex Machina |
| pair-010-en | en | a meticulous hotel concierge and his young lobby boy become entangled in a murder accusation over an inherited painting | The Grand Budapest Hotel | 200 | 2 | You Are My Spring |
| pair-010-fa | fa | یه مسئول پذیرش خیلی دقیق هتل همراه پادوی جوونش سر یه تابلوی نقاشی ارثی درگیر اتهام قتل میشن | The Grand Budapest Hotel | 200 | 2 | What's the Worst That Could Happen? |
| pair-011-en | en | a free black violinist is kidnapped after accepting a job and is sold into slavery despite insisting he is a free man | 12 Years a Slave | 200 | 1 | 12 Years a Slave |
| pair-011-fa | fa | یه نوازنده سیاهپوست آزاد رو بعد از قبول کردن یه کار میدزدن و میفروشن به بردگی در حالی که هی میگه من آدم آزادم | 12 Years a Slave | 200 | 1 | 12 Years a Slave |
| pair-012-en | en | a lone traveler carries a sacred book across a ruined America while a powerful man wants it to control other survivors | The Book of Eli | 200 | 1 | The Book of Eli |
| pair-012-fa | fa | یه مسافر تنها تو آمریکای ویران شده یه کتاب مقدس رو حمل میکنه و یه مرد قدرتمند میخواد کتاب رو بگیره تا بقیه بازمانده ها رو کنترل کنه | The Book of Eli | 200 | 1 | The Book of Eli |
| pair-013-en | en | a teenager receives audio tapes recorded by a girl who died and listens to her explanation of how people at school hurt her | 13 Reasons Why | 200 | 1 | 13 Reasons Why |
| pair-013-fa | fa | یه پسر نوجوان نوارهای صوتی دختری رو که مرده دریافت میکنه و میشنوه که بچه های مدرسه چطور بهش آسیب زدن | 13 Reasons Why | 200 | 1 | 13 Reasons Why |
| pair-014-en | en | a woman leaves her comfortable life for prison because of a crime from her past and encounters her former girlfriend there | Orange Is the New Black | 200 | 2 | Woman Thou Art Loosed |
| pair-014-fa | fa | یه زن به خاطر جرمی که سالها قبل کرده زندگی راحتش رو ول میکنه و میره زندان و اونجا دوست دختر سابقش رو میبینه | Orange Is the New Black | 200 | 2 | The Next Three Days |
| pair-015-en | en | a selfish woman arrives in what seems to be a perfect afterlife and tries to hide that she does not belong there | The Good Place | 200 | 1 | The Good Place |
| pair-015-fa | fa | یه زن خودخواه بعد از مرگ میره جایی که انگار بهشته و سعی میکنه قایم کنه که اصلا آدم خوبی نبوده و جاش اونجا نیست | The Good Place | 200 | 1 | The Good Place |
| pair-016-en | en | adult siblings are drawn back to the terrifying events of their childhood in a haunted house after another family tragedy | The Haunting of Hill House | 200 | 6 | Supernatural |
| pair-016-fa | fa | خواهر برادرهایی که بزرگ شدن بعد از یه اتفاق تلخ تو خانواده مجبور میشن دوباره با خاطرات ترسناک بچگیشون تو یه خونه تسخیر شده روبه رو بشن | The Haunting of Hill House | 200 | 6 | Lights Out |

### coverage

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |

### negative

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |

### ambiguous

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |

### invalid

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |

## Reproduce

Run the backend first; the runner reuses it and never loads a second copy of the models.

```powershell
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --preflight
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --output E:/CineSceneCache/cinescene/artifacts/broad-next.json
.\.venv\Scripts\python.exe scripts/summarize_broad_benchmark.py --input benchmarks/broad-latest.json --output benchmarks/broad-report.md
```

Use `--resume` with the same output/checkpoint after interruption; mismatched suites or engines are rejected. The configured system-drive free-space guard prevents starting another request when space is low. Windows paging can still grow temporarily on C during CPU inference even when model files and checkpoints are on E.

Suite SHA-256: `ae23d483ce06e1fd4015b71eac2e5ed3e71e8c6681ce76841a4fca9e0e3077f5`. Observed HTTP latency: median **15.202 s**, p95 **20.918 s**. This is not a controlled throughput/load benchmark, nor a benchmark of all inputs in browser WASM.
