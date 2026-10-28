# CineScene Broad Diagnostic

Completed **28/28 HTTP inputs** against `rrf-v11-resilient-bilingual`. Engine unchanged: **True**. Technical errors: **1**. Retrievals with reduced capabilities: **0**.

The engine policy is fixed during this run. Cases may have informed earlier development; this is a manual diagnostic sample, not a population accuracy estimate. All retrieval targets were checked by exact catalog ID before execution. Only the intended title is labeled; other plausible adaptations or related stories were not exhaustively judged. Source-informed episode checks, when present, are acceptance checks, not independent scene-recognition evidence.

Publication privacy: non-allowlisted local result labels/IDs are pseudonymized. Rankings and metrics are unchanged; original identities remain in the local checkpoint on E.

Manual bilingual diagnostic for recent film coverage and narrative retrieval, authored before running the expanded generation. Source-verified target identities, not independent population accuracy or timed-scene ground truth. No runtime tuning during this run.

## Retrieval

Canonical ID aliases were resolved from the attributed dataset's exact-title/main-cast reconciliation. Queries, intended titles and version labels were not rewritten. Remapped cases retain `original_expected_ids` in JSON; this is identity normalization, not substring or same-title fallback grading.

| Group | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| All retrieval inputs | 26 | 15 | 57.7% | 21 | 80.8% |
| Manual inputs only | 26 | 15 | 57.7% | 21 | 80.8% |
| en | 13 | 6 | 46.2% | 10 | 76.9% |
| fa | 13 | 9 | 69.2% | 11 | 84.6% |
| mixed | 0 | 0 | n/a | 0 | n/a |

Category and language groups overlap; do not add their counts together.

Persian first-choice concentration: **The Prince of Egypt** appears first in **1/13** queries. This is a diagnostic symptom, not proof of a single cause; no title-specific correction was applied.

| Category | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| movie_plot | 26 | 15 | 57.7% | 21 | 80.8% |

## Paired Language Check

The same 13 target stories were described in English and Persian. This is a stronger language comparison than comparing unrelated language samples.

| Language | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| en | 13 | 6 | 46.2% | 10 | 76.9% |
| fa | 13 | 9 | 69.2% | 11 | 84.6% |

Both first: **6**. English-only first: **0**. Persian-only first: **3**. Neither first: **4**.

## Coverage Check

Requested titles/versions, when present, deliberately probe coverage, including known weak areas. They are not a random sample of cinema. Movie remakes require the requested year. Series provider years are not treated as canonical premiere years. Aliases such as La Casa de Papel are resolved exactly.

| Requested title | Requested year | In catalog | Rank | Returned results despite absence |
| --- | --- | --- | --- | --- |

## Non-Retrieval Probes

Negative inputs should produce no movie suggestion or a clear input rejection. Ambiguous-probe passes mean only that the API returned multiple distinct suggestions, not that those suggestions were judged relevant. Invalid inputs must return HTTP 422.

| Kind | Inputs | Passed |
| --- | --- | --- |
| negative | 2 | 0 |
| ambiguous | 0 | 0 |
| invalid | 0 | 0 |

## Complete Input Ledger

Rank `not found` means absent from the ten returned results, not absent from the catalog. The full JSON retains all ten result identities. No private paths, transcripts or plot text are exported.

### retrieval

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| pair-001-en | en | an exiled young nobleman joins desert warriors, learns to ride enormous sandworms and becomes the focus of a dangerous religious uprising | Dune: Part Two | 200 | 6 | Dune |
| pair-001-fa | fa | یه جوان تبعیدی به مبارزهای صحرا ملحق میشه، یاد میگیره سوار کرم های غول پیکر شنی بشه و پیروانش اونو ناجی خودشون میدونن | Dune: Part Two | 200 | not found | The Prince of Egypt |
| pair-002-en | en | a physicist leads a secret wartime atomic bomb project and later faces a hearing about his loyalty and political connections | Oppenheimer | 200 | 1 | Oppenheimer |
| pair-002-fa | fa | یه فیزیکدان پروژه محرمانه ساخت بمب اتم در جنگ جهانی دوم رو رهبری میکنه و بعدا تو جلسه رسیدگی امنیتی بابت ارتباطات سیاسی اش بازخواست میشه | Oppenheimer | 200 | 1 | Oppenheimer |
| pair-003-en | en | a woman revived by an eccentric surgeon develops a new understanding of the world and escapes with a lawyer on a journey of discovery | Poor Things | 200 | 8 | Gonul |
| pair-003-fa | fa | یک جراح عجیب زنی رو به زندگی برمیگردونه که دوباره مثل بچه ها داره دنیا رو یاد میگیره و بعد با یه وکیل به سفر میره تا مستقل بشه | Poor Things | 200 | 2 | Woman Thou Art Loosed |
| pair-004-en | en | an aging television fitness celebrity uses an experimental treatment that creates a younger self, but the two must take turns living every week | The Substance | 200 | 1 | The Substance |
| pair-004-fa | fa | یک ستاره مسن برنامه ورزشی تلویزیون دارویی میگیره که نسخه جوان تری از خودش میسازه و باید هر هفته جای زندگی کردنشون رو با هم عوض کنن | The Substance | 200 | 1 | The Substance |
| pair-005-en | en | a Brooklyn sex worker impulsively marries the son of a wealthy Russian businessman and his family sends men to force an annulment | Anora | 500 | not found | no results |
| pair-005-fa | fa | یه دختر رقصنده تو بروکلین ناگهانی با پسر یک ثروتمند روس ازدواج میکنه و خانواده پسر چند نفر رو میفرستن تا ازدواجشون رو باطل کنن | Anora | 200 | 1 | Anora |
| pair-006-en | en | after the pope dies, a cardinal oversees a secret election in the Vatican while disturbing information about the candidates emerges | Conclave | 200 | 4 | Angels & Demons |
| pair-006-fa | fa | بعد از مرگ پاپ، یک کاردینال مسئول انتخابات محرمانه جانشین او تو واتیکان میشه و کم کم رازهای نامزدها رو میفهمه | Conclave | 200 | 2 | Angels & Demons |
| pair-007-en | en | a solitary black cat survives a devastating flood by sharing a small boat with other animals in a world without human dialogue | Flow | 200 | 1 | Flow |
| pair-007-fa | fa | یه گربه سیاه تو یک سیل بزرگ برای زنده موندن سوار قایقی میشه و مجبور میشه با چند حیوان دیگه همراه بشه، فیلم هم دیالوگ انسانی نداره | Flow | 200 | 1 | Flow |
| pair-008-en | en | twin brothers return to Mississippi to open a music club in the 1930s, but vampires threaten the people gathered there that night | Sinners | 200 | 1 | Sinners |
| pair-008-fa | fa | دو برادر دوقلو تو دهه سی میلادی به میسیسیپی برمیگردن و یک باشگاه موسیقی راه میندازن ولی همون شب خون آشام ها سراغ مهمونا میان | Sinners | 200 | 1 | Sinners |
| pair-009-en | en | nearly every child in one school class runs out of their homes at the same time during the night, leaving a teacher and one remaining pupil under suspicion | Weapons | 200 | 1 | Weapons |
| pair-009-fa | fa | تقریبا همه بچه های یک کلاس مدرسه در یک ساعت مشخص شب از خونه هاشون فرار میکنن و فقط یک دانش آموز باقی میمونه، بعد همه به معلم شک میکنن | Weapons | 200 | 1 | Weapons |
| pair-010-en | en | a Hungarian Jewish architect emigrates to America after the war and a wealthy patron commissions a monumental building that transforms his life | The Brutalist | 200 | 1 | The Brutalist |
| pair-010-fa | fa | یک معمار یهودی مجارستانی بعد از جنگ به آمریکا مهاجرت میکنه و یک سرمایه دار ثروتمند بهش سفارش ساخت بنای بزرگی میده که زندگیش رو عوض میکنه | The Brutalist | 200 | 1 | The Brutalist |
| pair-011-en | en | a lone astronaut wakes aboard a spacecraft with no memory, gradually remembers a mission to save the dying sun and befriends an alien facing the same problem | Project Hail Mary | 200 | 2 | Pandorum |
| pair-011-fa | fa | یک فضانورد تنها بدون حافظه توی سفینه بیدار میشه، کم کم یادش میاد باید خورشید در حال مرگ رو نجات بده و با یک موجود فضایی که مشکل مشابهی داره دوست میشه | Project Hail Mary | 200 | not found | Pandorum |
| pair-012-en | en | after the Trojan War a Greek king struggles to return to his wife and son while facing a cyclops and other dangers at sea | The Odyssey | 200 | 2 | Troy |
| pair-012-fa | fa | یک پادشاه یونانی بعد از جنگ تروا تلاش میکنه از راه دریا پیش همسر و پسرش برگرده ولی سر راه با غول یک چشم و خطرهای اسطوره ای روبرو میشه | The Odyssey | 200 | 1 | The Odyssey |
| pair-013-en | en | an officer that could raise to the life each time after he dies so he can fix the issues and keep soldiers alive and win the battle | Edge of Tomorrow | 200 | 2 | Glory |
| pair-013-fa | fa | یه افسر هر بار که تو جنگ با موجودات بیگانه کشته میشه دوباره همون روز رو از اول زندگی میکنه تا اشتباهاتش رو درست کنه و سربازها رو نجات بده | Edge of Tomorrow | 200 | 1 | Edge of Tomorrow |

### coverage

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |

### negative

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| negative-recent-en | en | how many teaspoons of salt should I use to cook plain rice | negative | 200 | not found | Salt Fat Acid Heat |
| negative-recent-fa | fa | برای پختن برنج ساده چند پیمانه آب بریزم | negative | 200 | not found | Signs |

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

Suite SHA-256: `e0a0bea8ee616a525cedd1eb72e05689cfa6c296a94bf597b611660498638384`. Observed HTTP latency: median **28.101 s**, p95 **54.732 s**. This is not a controlled throughput/load benchmark, nor a benchmark of all inputs in browser WASM.
