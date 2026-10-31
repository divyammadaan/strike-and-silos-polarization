# RQ4: text analysis of all comments (full dataset)

Comments analysed: 822,910 (june_2025: 334,797; feb_2026: 488,113), in 8,348 threads. Deleted and removed comments are excluded.

Comments mentioning at least one frame: june_2025 55.8%, feb_2026 52.4%.

## Frames mentioned (% of comments)

A comment can count for several frames. Intervals come from 1000 bootstrap resamples of whole threads; a change is 'clear' when the 95% interval of the difference excludes zero. With nine frames compared, treat marginal ones with caution.

| frame                        |   june_pct | june_95ci    |   feb_pct | feb_95ci     |   change_points | clear_change   |
|:-----------------------------|-----------:|:-------------|----------:|:-------------|----------------:|:---------------|
| Military events              |       25.5 | 24.8 to 26.3 |      24.8 | 24.2 to 25.4 |            -0.7 | no             |
| Israel and regional conflict |       21.3 | 20.3 to 22.6 |      10.8 | 10.3 to 11.3 |           -10.5 | yes            |
| US domestic politics         |       14.4 | 13.5 to 15.3 |      17   | 16.4 to 17.6 |             2.6 | yes            |
| Nuclear programme            |       10.2 | 9.5 to 10.9  |       2.8 | 2.6 to 3.1   |            -7.4 | yes            |
| Iranian regime and people    |        7.6 | 7.1 to 8.1   |       8   | 7.6 to 8.4   |             0.5 | no             |
| Legitimacy and morality      |        6.1 | 5.6 to 6.6   |       6   | 5.7 to 6.4   |            -0.1 | no             |
| Diplomacy and ceasefire      |        4.6 | 4.3 to 4.9   |       4.1 | 3.8 to 4.5   |            -0.5 | yes            |
| Media and information        |        4.6 | 4.4 to 4.8   |       4.3 | 4.2 to 4.5   |            -0.3 | yes            |
| Economy and energy           |        2.7 | 2.5 to 3.0   |       6.3 | 6.0 to 6.7   |             3.6 | yes            |

## Narrative similarity between subreddits

Mean pairwise cosine similarity of the subreddits' frame profiles (1 = identical mix of frames).

| window    |   frame_similarity | 95ci           |
|:----------|-------------------:|:---------------|
| june_2025 |              0.866 | 0.853 to 0.876 |
| feb_2026  |              0.877 | 0.864 to 0.886 |

## Frames by subreddit: june_2025 (% of comments)

|                              |   worldnews |   geopolitics |   Iran |   Israel |   NewIran |   IsraelPalestine |   politics |   Conservative |
|:-----------------------------|------------:|--------------:|-------:|---------:|----------:|------------------:|-----------:|---------------:|
| Military events              |        26.9 |          41   |   16.3 |     24.2 |      16.5 |              29.9 |       22.1 |           27.4 |
| Diplomacy and ceasefire      |         4.6 |           8.8 |    3.5 |      3.5 |       2.9 |               4.6 |        4.5 |            5   |
| US domestic politics         |        10.4 |          10.8 |    8.2 |      7.3 |       6.6 |               4.5 |       27.6 |           18.4 |
| Legitimacy and morality      |         4.8 |           6.1 |    6.3 |      4.5 |       7.2 |              19.3 |        4   |            3.2 |
| Iranian regime and people    |         6.6 |          10.6 |    9.3 |     12   |      25.9 |               8.7 |        3   |            7.2 |
| Israel and regional conflict |        20.2 |          32.4 |   22.1 |     32.3 |      20.7 |              51.6 |       11.5 |           17.8 |
| Economy and energy           |         3.1 |           5.6 |    2.7 |      1.7 |       1.9 |               1.6 |        2.5 |            2.4 |
| Nuclear programme            |        11.5 |          21.6 |    2.6 |      7   |       3.3 |              11.8 |        7.7 |           13.2 |
| Media and information        |         3.5 |           4.9 |    8   |      5.9 |       6.4 |               7.3 |        4.7 |            5.1 |

## Frames by subreddit: feb_2026 (% of comments)

|                              |   worldnews |   geopolitics |   Iran |   Israel |   NewIran |   IsraelPalestine |   politics |   Conservative |
|:-----------------------------|------------:|--------------:|-------:|---------:|----------:|------------------:|-----------:|---------------:|
| Military events              |        26.9 |          37.8 |   22.3 |     21.5 |      17.8 |              31.4 |       22   |           24.1 |
| Diplomacy and ceasefire      |         4.9 |           8.6 |    3.3 |      3.6 |       2.5 |               5.7 |        2.9 |            4   |
| US domestic politics         |        13.2 |          14.1 |   10.7 |      8.6 |       9.4 |               8   |       25.3 |           16.8 |
| Legitimacy and morality      |         5.5 |           6.1 |    7.5 |      5   |       5.7 |              17.7 |        6.1 |            3.9 |
| Iranian regime and people    |         7.1 |          13.4 |   10.3 |     14.3 |      23.4 |              13.4 |        4.1 |           11.6 |
| Israel and regional conflict |        10.2 |          19.4 |   16.1 |     28.8 |      12.6 |              45.8 |        7.6 |            9.1 |
| Economy and energy           |         7.6 |          12   |    4.8 |      3.6 |       3.1 |               3.5 |        5.1 |            5.3 |
| Nuclear programme            |         3   |           5.9 |    1.2 |      2.2 |       0.9 |               4.1 |        2.5 |            5.1 |
| Media and information        |         3.5 |           5.7 |    6.9 |      7.6 |       7.2 |               9   |        4.2 |            5.5 |

## Topic model (NMF, one document per thread)

Share of each window's comments in threads whose strongest topic is this one. Topics are numbered, not named: name them from their words.

|   topic | top_words                                                                                   |   june_2025 |   feb_2026 |
|--------:|:--------------------------------------------------------------------------------------------|------------:|-----------:|
|       1 | works, modern, entirely, multiple, weren, level, comment, type, outside, lmao               |        27.4 |       30.7 |
|       2 | translation, freedom, bot, woman, life, irgc, hope, live, internet, sub                     |         3.2 |        2.9 |
|       3 | president, maga, republicans, congress, epstein, democrats, vote, fucking, republican, shit |        14.4 |       23.9 |
|       4 | oil, strait, hormuz, prices, gas, ships, price, gulf, energy, tankers                       |         2   |       10.1 |
|       5 | nuclear, uranium, program, nukes, bomb, weapons, enriched, nuke, enrichment, facilities     |        22.6 |        2.2 |
|       6 | school, hit, missile, military, missiles, civilians, strike, target, civilian, targets      |         4.7 |        7.9 |
|       7 | jews, hamas, palestinians, jewish, gaza, palestine, palestinian, muslim, genocide, west     |        16.5 |        6.5 |
|       8 | kurds, pahlavi, change, iraq, ground, power, government, shah, irgc, kurdish                |         4.9 |        6.9 |
|       9 | russia, ukraine, putin, russian, china, drones, nato, allies, help, europe                  |         3.4 |        6.5 |
|      10 | giphy, gif, khamenei, leader, supreme, mojtaba, dead, ayatollah, downsized, alive           |         1   |        2.3 |

## Word lists

- **Military events:** strike* airstrike* attack* missile* drone* bomb* troops soldier* military army navy airforce intercept* retaliat* escalat* casualt* war warfare weapon* carrier* invasion
- **Diplomacy and ceasefire:** ceasefire* "cease fire" negotiat* diplomat* diplomacy "peace deal" "peace talks" talks treaty ally allies nato "united nations" sanctions mediat*
- **US domestic politics:** trump maga republican* democrat* gop congress senate senator* election* vote voter* voting biden harris obama impeach* "white house" hegseth vance rubio liberal* conservative*
- **Legitimacy and morality:** "war crime" "war crimes" illegal unlawful legal justified unjustified moral* immoral civilian* innocent* genocide "international law" constitution* hypocri* children murder*
- **Iranian regime and people:** regime khamenei ayatollah mullah* irgc "islamic republic" protest* protester* "iranian people" "people of iran" dictator* oppress* "regime change" pahlavi shah diaspora
- **Israel and regional conflict:** israel* idf netanyahu bibi gaza hamas hezbollah houthi* palestin* zionis* saudi* lebanon qatar syria iraq
- **Economy and energy:** oil "gas price" "gas prices" hormuz econom* market* inflation tanker* shipping recession tariff* "cost of living" dollar*
- **Nuclear programme:** nuclear nuke* uranium enrich* fordow natanz centrifuge* iaea "nuclear weapon" warhead*
- **Media and information:** media news propaganda misinformation disinformation fake bots "fox news" cnn bbc journalist* "source" censor* narrative*
