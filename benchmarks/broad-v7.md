# CineScene Broad Diagnostic

Completed **196/196 HTTP inputs** against `rrf-v7-passage-evidence`. Engine unchanged: **True**. Technical errors: **0**.

This run tests the existing engine without tuning it on these questions. It is a manual diagnostic sample, not a population accuracy estimate. All retrieval targets were checked by exact catalog ID before execution. Only the intended title is labeled; other plausible adaptations or related stories were not exhaustively judged. The 10 episode checks are source-informed acceptance checks, not independent scene-recognition evidence.

Publication privacy: non-allowlisted local result labels/IDs are pseudonymized. Rankings and metrics are unchanged; original identities remain in the local checkpoint on E.

## Retrieval

| Group | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| All retrieval inputs | 160 | 73 | 45.6% | 95 | 59.4% |
| Manual inputs only | 150 | 63 | 42.0% | 85 | 56.7% |
| en | 97 | 70 | 72.2% | 81 | 83.5% |
| fa | 61 | 2 | 3.3% | 13 | 21.3% |
| mixed | 2 | 1 | 50.0% | 1 | 50.0% |

Category and language groups overlap; do not add their counts together.

Persian first-choice concentration: **Private local title 1** appears first in **40/61** queries. This is a diagnostic symptom, not proof of a single cause; no title-specific correction was applied.

| Category | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| episode_identity | 10 | 10 | 100.0% | 10 | 100.0% |
| explicit_filter | 8 | 6 | 75.0% | 8 | 100.0% |
| movie_plot | 80 | 37 | 46.2% | 45 | 56.2% |
| noisy_input | 8 | 3 | 37.5% | 4 | 50.0% |
| scene_detail | 14 | 6 | 42.9% | 8 | 57.1% |
| series_plot | 40 | 11 | 27.5% | 20 | 50.0% |

## Paired Language Check

The same 60 target stories were described in English and Persian. This is a stronger language comparison than comparing unrelated language samples.

| Language | Inputs | First | Hit@1 | Top five | Hit@5 |
| --- | --- | --- | --- | --- | --- |
| en | 60 | 46 | 76.7% | 52 | 86.7% |
| fa | 60 | 2 | 3.3% | 13 | 21.7% |

Both first: **1**. English-only first: **45**. Persian-only first: **1**. Neither first: **13**.

## Coverage Check

These 20 requested titles/versions deliberately probe coverage, including known weak areas. They are not a random sample of cinema. Movie remakes require the requested year. Series provider years are not treated as canonical premiere years. Aliases such as La Casa de Papel are resolved exactly.

| Requested title | Requested year | In catalog | Rank | Returned results despite absence |
| --- | --- | --- | --- | --- |
| Arrival | 2016 | False | not found | True |
| Parasite | 2019 | False | not found | False |
| Everything Everywhere All at Once | 2022 | False | not found | False |
| Oppenheimer | 2023 | False | not found | False |
| Dune | 2021 | False | not found | False |
| Dune: Part Two | 2024 | False | not found | False |
| Predestination | 2014 | False | not found | True |
| Prison Break | 2005 | False | not found | True |
| House | 2004 | False | not found | True |
| Game of Thrones | 2011 | False | not found | True |
| Money Heist | 2017 | True | 1 | False |
| Lucifer | 2016 | False | not found | True |
| Vikings | 2013 | False | not found | True |
| Rick and Morty | 2013 | False | not found | True |
| The Big Bang Theory | 2007 | False | not found | True |
| How I Met Your Mother | 2005 | False | not found | True |
| The Boys | 2019 | False | not found | True |
| Wednesday | 2022 | False | not found | True |
| The Last of Us | 2023 | True | 1 | False |
| Fallout | 2024 | True | 1 | False |

## Non-Retrieval Probes

Negative inputs should produce no movie suggestion or a clear input rejection. Ambiguous-probe passes mean only that the API returned multiple distinct suggestions, not that those suggestions were judged relevant. Invalid inputs must return HTTP 422.

| Kind | Inputs | Passed |
| --- | --- | --- |
| negative | 4 | 0 |
| ambiguous | 4 | 4 |
| invalid | 8 | 8 |

## Complete Input Ledger

Rank `not found` means absent from the ten returned results, not absent from the catalog. The full JSON retains all ten result identities. No private paths, transcripts or plot text are exported.

### retrieval

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| pair-001-en | en | a commercial spaceship crew answers a distress call and a creature starts hunting them inside the ship | Alien | 200 | 1 | Alien |
| pair-001-fa | fa | خدمه یه سفینه باری به یک پیام کمک جواب میدن و بعد یه موجود بیگانه تو سفینه یکی یکی شکارشون میکنه | Alien | 200 | not found | Private local title 1 |
| pair-002-en | en | a woman returns with space marines to a colony overrun by aliens and tries to protect a little girl | Aliens | 200 | 1 | Aliens |
| pair-002-fa | fa | زنی همراه تفنگدارهای فضایی به یک مستعمره برمیگرده که موجودات بیگانه گرفتنش و میخواد یه دختر بچه رو نجات بده | Aliens | 200 | not found | Private local title 1 |
| pair-003-en | en | a killer machine is sent from the future to murder a waitress before she gives birth to a resistance leader | The Terminator | 200 | 1 | The Terminator |
| pair-003-fa | fa | یه ربات قاتل از آینده فرستاده میشه تا یک زن پیشخدمت رو قبل از به دنیا اومدن رهبر مقاومت بکشه | The Terminator | 200 | not found | Private local title 1 |
| pair-004-en | en | a reprogrammed robot protects a teenage boy from a more advanced liquid metal assassin | Terminator 2: Judgment Day | 200 | 1 | Terminator 2: Judgment Day |
| pair-004-fa | fa | یه ربات دوباره برنامه ریزی شده از یک پسر نوجوان در برابر قاتلی که از فلز مایع ساخته شده محافظت میکنه | Terminator 2: Judgment Day | 200 | not found | Red Dragon |
| pair-005-en | en | an elite rescue squad in a jungle discovers that an invisible alien hunter is stalking them | Predator | 200 | 1 | Predator |
| pair-005-fa | fa | یک گروه کماندو تو جنگل برای نجات گروگان میرن ولی یه شکارچی فضایی نامرئی دنبالشونه | Predator | 200 | not found | Furry Vengeance |
| pair-006-en | en | a winter caretaker moves his family into an isolated hotel where supernatural forces drive him toward violence | The Shining | 200 | 1 | The Shining |
| pair-006-fa | fa | یه نویسنده زمستون با زن و بچه اش نگهبان یک هتل دورافتاده میشه و کم کم تحت تاثیر نیروهای ماورایی خطرناک میشه | The Shining | 200 | not found | Private local title 1 |
| pair-007-en | en | a mother turns to priests when her young daughter appears to be possessed by a demonic presence | The Exorcist | 200 | 1 | The Exorcist |
| pair-007-fa | fa | یه مادر وقتی میبینه دختر کوچیکش رفتارهای وحشتناک و غیرطبیعی داره از کشیش ها برای بیرون کردن شیطان کمک میگیره | The Exorcist | 200 | not found | Private local title 1 |
| pair-008-en | en | two detectives pursue a murderer whose killings are arranged around the seven deadly sins | Se7en | 200 | 1 | Se7en |
| pair-008-fa | fa | دو کارآگاه دنبال قاتلی هستن که قتل هاش رو بر اساس هفت گناه کبیره طراحی کرده | Se7en | 200 | 3 | Murder by Numbers |
| pair-009-en | en | a young FBI trainee seeks advice from an imprisoned cannibal to catch another serial killer | The Silence of the Lambs | 200 | 1 | The Silence of the Lambs |
| pair-009-fa | fa | یه کارآموز زن اف بی آی برای پیدا کردن یک قاتل زنجیره ای از یه آدمخوار باهوش که زندانیه کمک میگیره | The Silence of the Lambs | 200 | not found | Penitentiary |
| pair-010-en | en | a seemingly timid survivor tells a customs agent how a group of criminals became entangled with a mysterious crime lord | The Usual Suspects | 200 | 1 | The Usual Suspects |
| pair-010-fa | fa | تنها بازمانده ظاهرا ضعیف یک ماجرای جنایی برای بازپرس تعریف میکنه که چطور چند خلافکار گرفتار یک تبهکار ناشناس شدن | The Usual Suspects | 200 | not found | Taxi Driver |
| pair-011-en | en | a mother keeps her light-sensitive children in a dark mansion and believes their home is haunted | The Others | 200 | 1 | The Others |
| pair-011-fa | fa | یک مادر بچه هاش رو که به نور حساسن توی عمارت تاریک نگه میداره و فکر میکنه خونه شون روح داره | The Others | 200 | not found | The Canyons |
| pair-012-en | en | a police officer infiltrates a Boston crime gang while a gangster's mole works inside the police department | The Departed | 200 | 1 | The Departed |
| pair-012-fa | fa | یک پلیس بین خلافکارهای بوستون نفوذ کرده و همزمان یکی از آدمهای رئیس باند داخل اداره پلیس جاسوسیه | The Departed | 200 | not found | Private local title 1 |
| pair-013-en | en | a teenage check forger impersonates a pilot and a doctor while an FBI agent follows his trail | Catch Me If You Can | 200 | 1 | Catch Me If You Can |
| pair-013-fa | fa | یه نوجوان با جعل چک خودش رو خلبان و پزشک جا میزنه و یک مامور اف بی آی مدام تعقیبش میکنه | Catch Me If You Can | 200 | not found | Private local title 1 |
| pair-014-en | en | the youngest son of a powerful mafia family is gradually drawn into his father's criminal empire | The Godfather | 200 | 2 | Corky Romano |
| pair-014-fa | fa | پسر کوچک یک خانواده مافیایی که اول نمیخواد وارد کارشون بشه کم کم اداره امپراتوری جنایی پدرش رو به دست میگیره | The Godfather | 200 | not found | Private local title 1 |
| pair-015-en | en | interwoven Los Angeles stories follow two hitmen, a boxer's escape and a gangster's wife in a nonlinear crime tale | Pulp Fiction | 200 | 1 | Pulp Fiction |
| pair-015-fa | fa | داستان غیرخطی چند خلافکار تو لس آنجلسه که ماجرای دو آدمکش و یک بوکسور و زن رئیس باند به هم وصل میشه | Pulp Fiction | 200 | not found | Private local title 1 |
| pair-016-en | en | after a jewelry robbery goes wrong surviving thieves meet in a warehouse and suspect one of them is an undercover cop | Reservoir Dogs | 200 | 1 | Reservoir Dogs |
| pair-016-fa | fa | بعد از خراب شدن سرقت جواهرفروشی دزدها توی یک انبار جمع میشن و شک میکنن یکی از خودشون پلیس مخفیه | Reservoir Dogs | 200 | not found | Private local title 1 |
| pair-017-en | en | a death row prison guard encounters a huge gentle inmate with a mysterious ability to heal people | The Green Mile | 200 | 1 | The Green Mile |
| pair-017-fa | fa | یک نگهبان بند اعدامی ها با زندانی خیلی درشت و مهربونی آشنا میشه که قدرت عجیبی برای شفا دادن آدمها داره | The Green Mile | 200 | not found | Fortress |
| pair-018-en | en | a delivery company employee survives a plane crash and spends years alone on a deserted island | Cast Away | 200 | 6 | Eden |
| pair-018-fa | fa | کارمند یک شرکت پستی بعد از سقوط هواپیما توی جزیره ای خالی از سکنه گیر میفته و سالها تنها زندگی میکنه | Cast Away | 200 | not found | The Apartment |
| pair-019-en | en | a struggling salesman becomes homeless with his young son while competing for an unpaid stockbroker internship | The Pursuit of Happyness | 200 | 1 | The Pursuit of Happyness |
| pair-019-fa | fa | یه پدر فروشنده با پسر کوچیکش بی خانمان میشه و همزمان برای کارآموزی بدون حقوق در یک شرکت بورس تلاش میکنه | The Pursuit of Happyness | 200 | not found | Private local title 1 |
| pair-020-en | en | a young shipwreck survivor shares a lifeboat with a Bengal tiger during a long journey across the ocean | Life of Pi | 200 | 1 | Life of Pi |
| pair-020-fa | fa | یک پسر بعد از غرق شدن کشتی مدت طولانی توی قایق نجات وسط اقیانوس با یک ببر بنگال تنها میمونه | Life of Pi | 200 | not found | Taxi Driver |
| pair-021-en | en | a boy raised in Mumbai's slums answers television quiz questions using memories from his difficult life | Slumdog Millionaire | 200 | 5 | Powder |
| pair-021-fa | fa | پسری که تو زاغه های بمبئی بزرگ شده توی مسابقه تلویزیونی جواب سوالها رو از خاطرات سخت زندگیش میدونه | Slumdog Millionaire | 200 | 6 | Private local title 1 |
| pair-022-en | en | a brilliant mathematician's life and marriage are disrupted by delusions and people who may not actually exist | A Beautiful Mind | 200 | not found | 21 Grams |
| pair-022-fa | fa | زندگی و ازدواج یک ریاضیدان نابغه به خاطر توهم و دیدن آدمهایی که واقعا وجود ندارن به هم میریزه | A Beautiful Mind | 200 | not found | Private local title 1 |
| pair-023-en | en | a British mathematician builds a machine with a secret wartime team to break encrypted German military messages | The Imitation Game | 200 | 1 | The Imitation Game |
| pair-023-fa | fa | یک ریاضیدان انگلیسی در جنگ جهانی دوم با یک تیم مخفی دستگاهی میسازه تا رمز پیامهای ارتش آلمان رو بشکنه | The Imitation Game | 200 | 4 | All The Queen's Men |
| pair-024-en | en | a Jewish pianist struggles to stay alive in Warsaw as the Nazis destroy the city and deport its residents | The Pianist | 200 | 1 | The Pianist |
| pair-024-fa | fa | یک پیانیست یهودی وقتی نازی ها ورشو رو ویران میکنن و مردم رو میبرن سعی میکنه پنهان بشه و زنده بمونه | The Pianist | 200 | not found | Private local title 1 |
| pair-025-en | en | a German businessman uses his factory and influence to save Jewish workers from Nazi extermination | Schindler's List | 200 | 1 | Schindler's List |
| pair-025-fa | fa | یک تاجر آلمانی از کارخانه و نفوذش استفاده میکنه تا کارگرهای یهودی رو از کشتار نازی ها نجات بده | Schindler's List | 200 | 2 | Private local title 1 |
| pair-026-en | en | after the Normandy landings a squad searches for a soldier whose brothers have all died in the war | Saving Private Ryan | 200 | 1 | Saving Private Ryan |
| pair-026-fa | fa | بعد از پیاده شدن نیروها در نرماندی یک گروه دنبال سربازی میگردن که همه برادرهاش در جنگ کشته شدن | Saving Private Ryan | 200 | not found | We Were Soldiers |
| pair-027-en | en | a girl volunteers in place of her younger sister for a televised contest where teenagers must kill each other | The Hunger Games | 200 | 1 | The Hunger Games |
| pair-027-fa | fa | یه دختر به جای خواهر کوچیکش داوطلب مسابقه تلویزیونی میشه که نوجوانها باید توش همدیگه رو بکشن | The Hunger Games | 200 | not found | Private local title 1 |
| pair-028-en | en | a boy with no memory arrives by elevator in a community of teenagers surrounded by an enormous changing maze | The Maze Runner | 200 | 1 | The Maze Runner |
| pair-028-fa | fa | یه پسر بی حافظه با آسانسور به جایی میرسه که چند نوجوان توش زندگی میکنن و دورش یک هزارتوی بزرگ و متغیره | The Maze Runner | 200 | not found | Private local title 1 |
| pair-029-en | en | aliens live in a segregated camp near Johannesburg and a bureaucrat exposed to their technology starts transforming | District 9 | 200 | 1 | District 9 |
| pair-029-fa | fa | فضایی ها توی اردوگاه جداشده نزدیک ژوهانسبورگ زندگی میکنن و یک کارمند که با موادشون تماس پیدا میکنه کم کم تبدیل به یکی از اونها میشه | District 9 | 200 | not found | Private local title 1 |
| pair-030-en | en | a lone worker nearing the end of his lunar mining contract discovers another version of himself at the base | Moon | 200 | 1 | Moon |
| pair-030-fa | fa | کارگری که نزدیک پایان قراردادش روی ماه تنها کار میکنه یک نسخه دیگه از خودش رو توی پایگاه پیدا میکنه | Moon | 200 | not found | Taxi Driver |
| pair-031-en | en | the wealthy live on a luxurious space habitat while a sick man on ruined Earth tries to reach its medical technology | Elysium | 200 | 1 | Elysium |
| pair-031-fa | fa | ثروتمندها روی یک ایستگاه فضایی لوکس زندگی میکنن و مردی بیمار روی زمین ویران شده میخواد به دستگاه های درمانی اونجا برسه | Elysium | 200 | 2 | Private local title 1 |
| pair-032-en | en | a drone repairman on an abandoned Earth questions his mission after finding a woman in a crashed spacecraft | Oblivion | 200 | 1 | Oblivion |
| pair-032-fa | fa | تعمیرکار پهپادها روی زمین خالی از انسان بعد از پیدا کردن زنی توی سفینه سقوط کرده به ماموریت خودش شک میکنه | Oblivion | 200 | not found | Private local title 1 |
| pair-033-en | en | a police unit uses visions of future murders until its own chief is predicted to commit a killing | Minority Report | 200 | 1 | Minority Report |
| pair-033-fa | fa | یک واحد پلیس با پیش بینی قتل های آینده جلوی جرم رو میگیره تا اینکه خود رئیسش به عنوان قاتل آینده معرفی میشه | Minority Report | 200 | not found | I AM A KILLER |
| pair-034-en | en | a hired killer executes people sent back through time until his next target turns out to be his older self | Looper | 200 | 1 | Looper |
| pair-034-fa | fa | یه آدمکش کسانی رو که از آینده به گذشته میفرستن میکشه تا اینکه هدف بعدی خودش در سن بالاتره | Looper | 200 | not found | Private local title 1 |
| pair-035-en | en | a lonely man forms a romantic relationship with the voice of an intelligent computer operating system | Her | 200 | 1 | Her |
| pair-035-fa | fa | یه مرد تنها عاشق صدای یک سیستم عامل هوشمند کامپیوتری میشه و باهاش رابطه عاطفی پیدا میکنه | Her | 200 | 1 | Her |
| pair-036-en | en | after a breakup a man has memories of his girlfriend erased but tries to hold onto them during the procedure | Eternal Sunshine of the Spotless Mind | 200 | 1 | Eternal Sunshine of the Spotless Mind |
| pair-036-fa | fa | یک مرد بعد از جدایی خاطرات دوست دخترش رو از مغزش پاک میکنه ولی وسط فرایند میخواد خاطرات رو حفظ کنه | Eternal Sunshine of the Spotless Mind | 200 | not found | Private local title 1 |
| pair-037-en | en | an elderly widower lifts his house into the sky with balloons and discovers a boy scout has come along | Up | 200 | 1 | Up |
| pair-037-fa | fa | یک پیرمرد بعد از مرگ همسرش خونه اش رو با کلی بادکنک به پرواز درمیاره و میفهمه یه پسر پیشاهنگ هم همراهشه | Up | 200 | not found | Private local title 1 |
| pair-038-en | en | a rat who loves cooking secretly controls a clumsy kitchen worker to prepare food in a Paris restaurant | Ratatouille | 200 | 1 | Ratatouille |
| pair-038-fa | fa | یه موش که عاشق آشپزیه مخفیانه حرکات یک کارگر دست و پا چلفتی آشپزخونه رو کنترل میکنه تا توی رستوران پاریس غذا بپزن | Ratatouille | 200 | 2 | Private local title 1 |
| pair-039-en | en | two monsters who collect energy by frightening children must return a little girl who enters their world | Monsters, Inc. | 200 | 1 | Monsters, Inc. |
| pair-039-fa | fa | دو هیولا که با ترسوندن بچه ها انرژی جمع میکنن باید دختر کوچولویی رو که وارد دنیای اونا شده به خونه برگردونن | Monsters, Inc. | 200 | not found | Private local title 1 |
| pair-040-en | en | a girl enters a spirit world and works in a bathhouse to rescue her parents who have been turned into pigs | Spirited Away | 200 | 1 | Spirited Away |
| pair-040-fa | fa | یه دختر وارد دنیای ارواح میشه و توی حمام اونها کار میکنه تا پدر و مادرش رو که به خوک تبدیل شدن نجات بده | Spirited Away | 200 | 4 | Private local title 1 |
| pair-041-en | en | a ruthless American congressman and his equally ambitious wife manipulate their way toward the presidency | House of Cards | 200 | 8 | Primary Colors |
| pair-041-fa | fa | یک نماینده بی رحم کنگره آمریکا با همسر جاه طلبش با دسیسه و سوءاستفاده میخوان به ریاست جمهوری برسن | House of Cards | 200 | not found | Private local title 1 |
| pair-042-en | en | American drug agents pursue Colombian cocaine kingpins as the Medellin cartel grows in power | Narcos | 200 | 6 | Undercover Law |
| pair-042-fa | fa | مامورهای مبارزه با مواد مخدر آمریکا دنبال قاچاقچی های کوکائین کلمبیا هستن و قدرت کارتل مدلین بیشتر میشه | Narcos | 200 | not found | Private local title 1 |
| pair-043-en | en | two brothers drive across America hunting demons, ghosts and other creatures while investigating their family's past | Supernatural | 200 | 1 | Supernatural |
| pair-043-fa | fa | دو برادر با ماشین تو آمریکا میگردن و ارواح و شیاطین و موجودات عجیب رو شکار میکنن و دنبال راز گذشته خانواده شون هستن | Supernatural | 200 | not found | Drive |
| pair-044-en | en | a sheriff awakens from a coma after a zombie outbreak and leads survivors searching for safety | The Walking Dead | 200 | 9 | The Walking Deceased |
| pair-044-fa | fa | یک کلانتر از کما بیدار میشه و میبینه دنیا پر از زامبی شده و رهبری گروهی از بازمانده ها رو به عهده میگیره | The Walking Dead | 200 | not found | Private local title 1 |
| pair-045-en | en | a documentary camera crew follows the awkward manager and employees of a Pennsylvania paper company | The Office (U.S.) | 200 | 2 | Spice World |
| pair-045-fa | fa | دوربین یک مستند زندگی روزمره مدیر عجیب و کارمندهای یک شرکت کاغذفروشی در پنسیلوانیا رو دنبال میکنه | The Office (U.S.) | 200 | 1 | The Office (U.S.) |
| pair-046-en | en | a washed-up horse actor from a once popular sitcom struggles with addiction and loneliness in Hollywood | BoJack Horseman | 200 | 1 | BoJack Horseman |
| pair-046-fa | fa | یک اسب بازیگر که قبلا ستاره یک سریال کمدی بوده توی هالیوود با اعتیاد و تنهایی و شکست هاش دست و پنجه نرم میکنه | BoJack Horseman | 200 | not found | The Bear |
| pair-047-en | en | a young airbender must master all four elements to stop a fire nation from conquering the world | Avatar: The Last Airbender | 200 | 2 | The Last Airbender |
| pair-047-fa | fa | یک پسر بادافزار باید کنترل هر چهار عنصر رو یاد بگیره تا جلوی فتح دنیا توسط ملت آتش رو بگیره | Avatar: The Last Airbender | 200 | not found | Private local title 1 |
| pair-048-en | en | an armored bounty hunter in the Star Wars galaxy protects a mysterious child instead of handing him over | The Mandalorian | 200 | not found | Star Wars: Episode II - Attack of the Clones |
| pair-048-fa | fa | یک شکارچی جایزه بگیر زره پوش توی دنیای جنگ ستارگان به جای تحویل دادن یک بچه مرموز ازش محافظت میکنه | The Mandalorian | 200 | not found | Dr. No |
| pair-049-en | en | people drowning in debt compete in children's games that kill the losers for a huge cash prize | Squid Game | 200 | 1 | Squid Game |
| pair-049-fa | fa | آدمهای بدهکار برای یک جایزه نقدی بزرگ توی بازیهای بچگانه شرکت میکنن ولی هر کس ببازه کشته میشه | Squid Game | 200 | 2 | Private local title 1 |
| pair-050-en | en | a financial adviser moves his family to a lake resort region to launder money for a drug cartel | Ozark | 200 | 1 | Ozark |
| pair-050-fa | fa | یک مشاور مالی خانواده اش رو به منطقه ای کنار دریاچه میبره تا برای یک کارتل مواد مخدر پولشویی کنه | Ozark | 200 | 2 | Private local title 1 |
| pair-051-en | en | a seemingly charming bookstore manager stalks women he becomes obsessed with and removes people in his way | You | 200 | 1 | You |
| pair-051-fa | fa | یک مدیر کتابفروشی که ظاهر جذابی داره زنهایی رو که بهشون وسواس پیدا میکنه تعقیب میکنه و آدمهای سر راهش رو از بین میبره | You | 200 | not found | The Pursuit of D.B. Cooper |
| pair-052-en | en | adopted siblings with strange powers reunite after their father's death and try to prevent an apocalypse | The Umbrella Academy | 200 | 1 | The Umbrella Academy |
| pair-052-fa | fa | خواهر و برادرهای فرزندخوانده با قدرتهای عجیب بعد از مرگ پدرشون دوباره جمع میشن تا جلوی آخرالزمان رو بگیرن | The Umbrella Academy | 200 | 3 | Private local title 1 |
| pair-053-en | en | an orphaned girl becomes a chess prodigy while fighting dependence on tranquilizers and alcohol | The Queen's Gambit | 200 | 1 | The Queen's Gambit |
| pair-053-fa | fa | یک دختر یتیم نابغه شطرنج میشه ولی همزمان با وابستگی به قرص آرامبخش و الکل مبارزه میکنه | The Queen's Gambit | 200 | not found | Private local title 1 |
| pair-054-en | en | scientists and workers struggle to contain a Soviet nuclear reactor disaster while officials hide what happened | Chernobyl | 200 | 2 | The Sum of All Fears |
| pair-054-fa | fa | دانشمندها و کارگرها تلاش میکنن فاجعه یک راکتور هسته ای شوروی رو مهار کنن ولی مقامها حقیقت رو پنهان میکنن | Chernobyl | 200 | 2 | Private local title 1 |
| pair-055-en | en | a thief living under the Galactic Empire is gradually drawn into an organized rebellion | Andor | 200 | 2 | The Empire Strikes Back |
| pair-055-fa | fa | یک دزد که زیر سلطه امپراتوری کهکشانی زندگی میکنه کم کم وارد جنبش سازمان یافته شورشی ها میشه | Andor | 200 | not found | The Ice Pirates |
| pair-056-en | en | a sheltered woman leaves an underground vault and travels through a radioactive wasteland searching for her father | Fallout | 200 | 6 | Blast from the Past |
| pair-056-fa | fa | یک دختر که توی پناهگاه زیرزمینی بزرگ شده برای پیدا کردن پدرش وارد سرزمین ویران و رادیواکتیو بیرون میشه | Fallout | 200 | not found | Private local title 1 |
| pair-057-en | en | a hardened smuggler escorts an immune teenage girl across a country devastated by a fungal infection | The Last of Us | 200 | 1 | The Last of Us |
| pair-057-fa | fa | یک قاچاقچی خشن باید دختر نوجوانی رو که به عفونت قارچی مصونه از کشوری که آلوده ها نابودش کردن عبور بده | The Last of Us | 200 | not found | Private local title 1 |
| pair-058-en | en | a socially isolated cybersecurity engineer is recruited by hackers to attack the corporation that controls much of society | Mr. Robot | 200 | 1 | Mr. Robot |
| pair-058-fa | fa | یک مهندس امنیت سایبری گوشه گیر توسط گروه هکرها جذب میشه تا به شرکت بزرگی که روی جامعه سلطه داره حمله کنه | Mr. Robot | 200 | 7 | Hackers |
| pair-059-en | en | families in a German town discover that missing children and a cave connect events across different generations | Dark | 200 | 1 | Dark |
| pair-059-fa | fa | چند خانواده توی یک شهر آلمانی میفهمن گم شدن بچه ها و یک غار اتفاقهای نسلهای مختلف رو به هم وصل میکنه | Dark | 200 | 2 | Private local title 1 |
| pair-060-en | en | separate unsettling stories examine how new devices and digital systems distort human relationships | Black Mirror | 200 | not found | Hot Girls Wanted: Turned On |
| pair-060-fa | fa | هر قسمت یک داستان جداست که نشون میده ابزارهای دیجیتال و فناوری جدید چطور روابط انسانها رو به شکل نگران کننده تغییر میدن | Black Mirror | 200 | not found | Private local title 1 |
| scene-01 | en | visitors ride in transparent rolling spheres while a genetically engineered dinosaur escapes the park | Jurassic World | 200 | 2 | Jurassic Park |
| scene-02 | en | a little boy rides his tricycle through a hotel and sees two identical girls standing in the corridor | The Shining | 200 | not found | Mama |
| scene-03 | en | a wife discovers that every page her husband has typed repeats the same sentence about work and play | The Shining | 200 | not found | Black Mirror |
| scene-04 | en | a detective receives a box in the desert and a serial killer reveals that it contains his wife's head | Se7en | 200 | 9 | Triple 9 |
| scene-05 | en | a captive woman at the bottom of a pit is ordered to rub lotion on her skin | The Silence of the Lambs | 200 | not found | Apocalypto |
| scene-06 | en | after an interrogation an officer realizes the suspect invented names from objects around the room and drops his coffee cup | The Usual Suspects | 200 | 3 | Criminal: UK |
| scene-07 | en | a movie producer wakes in his bed and finds the severed head of his prized horse under the sheets | The Godfather | 200 | not found | Scary Movie 5 |
| scene-08 | en | a gangster's wife overdoses and a man plunges an adrenaline needle into her chest to revive her | Pulp Fiction | 200 | 1 | Pulp Fiction |
| scene-09 | en | an isolated island survivor talks to a volleyball with a painted face and is devastated when it floats away | Cast Away | 200 | 1 | Cast Away |
| scene-10 | en | a shipwrecked boy and a tiger reach a floating island full of meerkats that becomes dangerous at night | Life of Pi | 200 | 1 | Life of Pi |
| scene-11 | en | a fugitive has his eyes replaced to evade retinal scanners while mechanical spiders search the building | Minority Report | 200 | not found | They Live |
| scene-12 | en | a man discovers his artificial intelligence girlfriend is simultaneously talking to thousands of other people | Her | 200 | 1 | Her |
| scene-13 | en | a couple lie together on a frozen river while memories of their relationship are being erased | Eternal Sunshine of the Spotless Mind | 200 | 1 | Eternal Sunshine of the Spotless Mind |
| scene-14 | en | a girl's parents greedily eat food at an abandoned restaurant and are transformed into pigs | Spirited Away | 200 | 1 | Spirited Away |
| robust-01 | en | that one with the alen on the cargo spaceshp and the crew cant get rid of it | Alien | 200 | 8 | Cargo |
| robust-02 | en | a robbot made of liquid mettal chases a kid but another machine is protecting him | Terminator 2: Judgment Day | 200 | 1 | Terminator 2: Judgment Day |
| robust-03 | en | dude works alone on the moon and finds out theres another him | Moon | 200 | 1 | Moon |
| robust-04 | en | big shark beach town police chief hunting it on a boat | Jaws | 200 | 2 | Jaws 2 |
| robust-05 | mixed | یه hacker تنها که گروه fsociety میخوان بدهی مردم رو با هک کردن شرکت پاک کنن | Mr. Robot | 200 | 1 | Mr. Robot |
| robust-06 | fa | موشه میره زیر کلاه آشپزه و با کشیدن موهاش دستاشو تکون میده | Ratatouille | 200 | not found | Private local title 1 |
| robust-07 | en | roman genral gets betrayed then fights as a slave in the arena | Gladiator | 200 | 6 | Pompeii |
| robust-08 | mixed | یه مامور تو سیستم precrime خودش به عنوان قاتل آینده شناسایی میشه | Minority Report | 200 | 10 | Private local title 1 |
| filter-01 | en | a machine sent back in time to kill a future leader's mother released in 1984 | The Terminator | 200 | 1 | The Terminator |
| filter-02 | en | a robot protects a boy against a liquid metal killer from 1991 | Terminator 2: Judgment Day | 200 | 1 | Terminator 2: Judgment Day |
| filter-03 | en | Severance released in 2022 | Severance | 200 | 1 | Severance |
| filter-04 | en | Severance from 2006 | Severance | 200 | 1 | Severance |
| filter-05 | en | a marine explores the world of blue aliens directed by James Cameron | Avatar | 200 | 1 | Avatar |
| filter-06 | en | a boy must learn to control water earth fire and air | Avatar: The Last Airbender | 200 | 4 | EDENS ZERO |
| filter-07 | en | Silo released in 2023 | Silo | 200 | 1 | Silo |
| filter-08 | en | a killer robot comes from the future science fiction without horror | The Terminator | 200 | 3 | Bill & Ted's Bogus Journey |
| episode-01 | en | Elliot is invited to join an underground hacking group that wants to destroy the corporation he protects at work | Mr. Robot S01E01 | 200 | 1 | Mr. Robot |
| episode-02 | en | Cobel introduces new security restrictions that Mark and his office team must deal with | Severance S01E07 | 200 | 1 | Severance |
| episode-03 | en | in 2019 a boy disappears in Winden and residents fear the town's tragic history is repeating | Dark S01E01 | 200 | 1 | Dark |
| episode-04 | en | nine-year-old Beth learns chess in an orphanage and becomes dependent on the green pills given to children | The Queen's Gambit S01E01 | 200 | 1 | The Queen's Gambit |
| episode-05 | en | a stranger comes to survivalist Bill's compound and they form an unexpected bond before Joel and Ellie arrive for help | The Last of Us S01E03 | 200 | 1 | The Last of Us |
| episode-06 | en | Cassian and the other prisoners finally get a rare opening to act together against their captors | Andor S01E10 | 200 | 1 | Andor |
| episode-07 | en | Ulana Khomyuk urgently tries to warn Legasov that a second nuclear explosion could threaten the continent | Chernobyl S01E02 | 200 | 1 | Chernobyl |
| episode-08 | en | Sheriff Becker's plans change after his wife meets a hacker who knows something about their underground home | Silo S01E01 | 200 | 1 | Silo |
| episode-09 | en | Dolores believes she lives freely in the Old West while the park managers notice their androids behaving unexpectedly | Westworld S01E01 | 200 | 1 | Westworld |
| episode-10 | en | people trapped in endless physical labor see a televised talent competition called Hot Shot as their only escape | Black Mirror S01E02 | 200 | 1 | Black Mirror |

### coverage

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| coverage-01 | en | a linguist deciphers the circular written language of aliens visiting Earth released in 2016 | Arrival | 200 | not found | Independence Day: Resurgence |
| coverage-02 | en | a poor family infiltrates a wealthy household by secretly taking different jobs there released in 2019 | Parasite | 200 | not found | no results |
| coverage-03 | en | a laundromat owner accesses alternate versions of herself while her family faces a multiverse crisis released in 2022 | Everything Everywhere All at Once | 200 | not found | no results |
| coverage-04 | en | the physicist leading the atomic bomb project later faces a hearing about his security clearance released in 2023 | Oppenheimer | 200 | not found | no results |
| coverage-05 | en | a young heir moves to a desert planet where giant sandworms and a valuable spice shape a political struggle released in 2021 | Dune | 200 | not found | no results |
| coverage-06 | en | Paul joins the desert people and their holy war while riding giant sandworms released in 2024 | Dune: Part Two | 200 | not found | no results |
| coverage-07 | en | a time-travelling agent's pursuit of a bomber becomes entangled with the life of an intersex writer released in 2014 | Predestination | 200 | not found | Interstellar |
| coverage-08 | en | an engineer deliberately enters prison to rescue his brother using a building plan tattooed on his body | Prison Break | 200 | not found | Nowhere Man |
| coverage-09 | en | a sarcastic doctor with a painful leg leads a team diagnosing baffling medical cases | House | 200 | not found | Case Closed |
| coverage-10 | en | noble families fight for an iron throne while an undead army threatens them from the north | Game of Thrones | 200 | not found | Giri / Haji |
| coverage-11 | en | robbers with city code names follow a professor's plan to occupy Spain's royal mint | Money Heist | 200 | 1 | La casa de papel |
| coverage-12 | en | the devil leaves Hell to run a nightclub and helps a Los Angeles detective investigate murders | Lucifer | 200 | not found | City of Ghosts |
| coverage-13 | en | a Norse farmer named Ragnar becomes a raider and leader seeking new lands across the sea | Vikings | 200 | not found | Ragnarok |
| coverage-14 | en | a cynical scientist takes his anxious grandson on adventures through portals to other dimensions | Rick and Morty | 200 | not found | Stranger Things |
| coverage-15 | en | socially awkward physicists share an apartment across the hall from an aspiring actress | The Big Bang Theory | 200 | not found | Followers |
| coverage-16 | en | a father tells his children a long story about his New York friends and how he met their mother | How I Met Your Mother | 200 | not found | Mr. Robot |
| coverage-17 | en | ordinary vigilantes try to expose violent and corrupt celebrity superheroes controlled by a corporation | The Boys | 200 | not found | Private Lives |
| coverage-18 | en | a deadpan girl from the Addams family investigates a monster while attending a school for outcasts | Wednesday | 200 | not found | AlRawabi School for Girls |
| coverage-19 | en | a smuggler escorts an immune girl across an America devastated by a fungus | The Last of Us | 200 | 1 | The Last of Us |
| coverage-20 | en | a vault dweller leaves her protected underground home to search the nuclear wasteland for her father | Fallout | 200 | 1 | Fallout |

### negative

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| negative-01 | n/a | zxqvplm nkrtjfw qzxxvbn | negative | 200 | not found | Private local title 1 |
| negative-02 | n/a | ۷۶۵۴۳۲۱۰ ۹۹۸۸۷۷۶۶ | negative | 200 | not found | Human Traffic |
| negative-03 | n/a | what is seventeen multiplied by twenty three | negative | 200 | not found | 24 7: Twenty Four Seven |
| negative-04 | n/a | برای پختن برنج تو قابلمه چند پیمانه آب بریزم | negative | 200 | not found | Private local title 1 |

### ambiguous

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| ambiguous-01 | n/a | a person travels through time | ambiguous | 200 | not found | Kate & Leopold |
| ambiguous-02 | n/a | a detective investigates a murder | ambiguous | 200 | not found | Day and Night |
| ambiguous-03 | n/a | یه فیلم که چند نفر تو فضا هستن | ambiguous | 200 | not found | Space Racers |
| ambiguous-04 | n/a | a funny story about a group of friends | ambiguous | 200 | not found | It's Kind of a Funny Story |

### invalid

| ID | Language | Actual input | Expected | HTTP | Rank | First result |
| --- | --- | --- | --- | --- | --- | --- |
| invalid-01 | n/a |  | invalid | 422 | not found | no results |
| invalid-02 | n/a |     | invalid | 422 | not found | no results |
| invalid-03 | n/a | [input length 1001; full content in JSON] | invalid | 422 | not found | no results |
| invalid-04 | n/a | a scene | invalid | 422 | not found | no results |
| invalid-05 | n/a | a scene | invalid | 422 | not found | no results |
| invalid-06 | n/a | a scene | invalid | 422 | not found | no results |
| invalid-07 | n/a | a scene | invalid | 422 | not found | no results |
| invalid-08 | n/a | not found | invalid | 422 | not found | no results |

## Reproduce

Run the backend first; the runner reuses it and never loads a second copy of the models.

```powershell
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --preflight
.\.venv\Scripts\python.exe scripts/broad_retrieval_benchmark.py --output E:/CineSceneCache/cinescene/artifacts/broad-next.json
.\.venv\Scripts\python.exe scripts/summarize_broad_benchmark.py --input benchmarks/broad-latest.json --output benchmarks/broad-report.md
```

Use `--resume` with the same output/checkpoint after interruption; mismatched suites or engines are rejected. A 2 GB system-drive free-space guard prevents starting another request when space is low. Windows paging can still grow temporarily on C during CPU inference even when model files and checkpoints are on E.

Suite SHA-256: `088469494d318efa3abe2724cff013497950e5d978b91c4405164994d9daf00f`. Observed HTTP latency: median **5.02 s**, p95 **6.026 s**. This is not a controlled throughput/load benchmark, nor a benchmark of all inputs in browser WASM.
