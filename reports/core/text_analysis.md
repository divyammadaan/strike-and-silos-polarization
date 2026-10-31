# RQ4: text analysis of all comments (core dataset)

Comments analysed: 709,765 (june_2025: 292,735; feb_2026: 417,030), in 3,378 threads. Deleted and removed comments are excluded.

Comments mentioning at least one frame: june_2025 56.1%, feb_2026 52.5%.

## Frames mentioned (% of comments)

A comment can count for several frames. Intervals come from 1000 bootstrap resamples of whole threads; a change is 'clear' when the 95% interval of the difference excludes zero. With nine frames compared, treat marginal ones with caution.

| frame                        |   june_pct | june_95ci    |   feb_pct | feb_95ci     |   change_points | clear_change   |
|:-----------------------------|-----------:|:-------------|----------:|:-------------|----------------:|:---------------|
| Military events              |       26.2 | 25.4 to 27.0 |      25.2 | 24.5 to 25.9 |            -1   | no             |
| Israel and regional conflict |       21.1 | 20.0 to 22.4 |      10.5 | 10.0 to 11.1 |           -10.6 | yes            |
| US domestic politics         |       14.5 | 13.5 to 15.5 |      17.2 | 16.5 to 17.9 |             2.7 | yes            |
| Nuclear programme            |       10.8 | 9.9 to 11.6  |       2.9 | 2.6 to 3.3   |            -7.8 | yes            |
| Iranian regime and people    |        6.9 | 6.4 to 7.4   |       7.3 | 6.9 to 7.7   |             0.4 | no             |
| Legitimacy and morality      |        5.9 | 5.4 to 6.5   |       6.1 | 5.7 to 6.5   |             0.2 | no             |
| Diplomacy and ceasefire      |        4.7 | 4.3 to 5.1   |       4.2 | 3.9 to 4.6   |            -0.5 | no             |
| Media and information        |        4.4 | 4.2 to 4.6   |       4.1 | 3.9 to 4.3   |            -0.3 | yes            |
| Economy and energy           |        2.8 | 2.5 to 3.1   |       6.5 | 6.0 to 6.9   |             3.7 | yes            |

## Narrative similarity between subreddits

Mean pairwise cosine similarity of the subreddits' frame profiles (1 = identical mix of frames).

| window    |   frame_similarity | 95ci           |
|:----------|-------------------:|:---------------|
| june_2025 |              0.873 | 0.856 to 0.883 |
| feb_2026  |              0.881 | 0.865 to 0.890 |

## Frames by subreddit: june_2025 (% of comments)

|                              |   worldnews |   geopolitics |   Iran |   Israel |   NewIran |   IsraelPalestine |   politics |   Conservative |
|:-----------------------------|------------:|--------------:|-------:|---------:|----------:|------------------:|-----------:|---------------:|
| Military events              |        27   |          40.7 |   16   |     24.9 |      18   |              31.5 |       22.1 |           29.1 |
| Diplomacy and ceasefire      |         4.6 |           8.7 |    4   |      3.5 |       2.6 |               4.8 |        4.4 |            5.1 |
| US domestic politics         |        10.4 |          10.7 |    9.1 |      8   |       7.7 |               4.6 |       27.1 |           18.3 |
| Legitimacy and morality      |         4.8 |           6.2 |    6.5 |      4.2 |       8.9 |              19.3 |        4   |            3.3 |
| Iranian regime and people    |         6.6 |          10.5 |    9.9 |     12.6 |      26.6 |               9.3 |        2.9 |            6.7 |
| Israel and regional conflict |        20.2 |          32.5 |   21.7 |     33.1 |      23.8 |              51.5 |       11.3 |           18.8 |
| Economy and energy           |         3   |           5.6 |    2.6 |      1.8 |       1.4 |               1.6 |        2.4 |            2.5 |
| Nuclear programme            |        11.6 |          21.4 |    2.4 |      7.3 |       3.4 |              13.8 |        7.7 |           14.3 |
| Media and information        |         3.5 |           4.8 |    7.7 |      6   |       6.8 |               7   |        4.7 |            4.8 |

## Frames by subreddit: feb_2026 (% of comments)

|                              |   worldnews |   geopolitics |   Iran |   Israel |   NewIran |   IsraelPalestine |   politics |   Conservative |
|:-----------------------------|------------:|--------------:|-------:|---------:|----------:|------------------:|-----------:|---------------:|
| Military events              |        27   |          37.8 |   23.5 |     20.8 |      16.9 |              30.9 |       21.6 |           26.1 |
| Diplomacy and ceasefire      |         4.9 |           8.4 |    3.2 |      3.5 |       2.3 |               4.3 |        2.8 |            4.5 |
| US domestic politics         |        13.3 |          14.3 |   12.5 |      7.8 |      11.3 |               8.4 |       25.1 |           17.4 |
| Legitimacy and morality      |         5.6 |           6.3 |    7.5 |      5.6 |       5.9 |              17.4 |        6.3 |            3.8 |
| Iranian regime and people    |         7.1 |          13.4 |   12.3 |     15.3 |      22.7 |              14.5 |        4   |           11.5 |
| Israel and regional conflict |        10.1 |          19   |   15.8 |     28.1 |      14   |              44.1 |        7.4 |            9.9 |
| Economy and energy           |         7.6 |          11.7 |    5   |      3.1 |       2.8 |               3.6 |        4.7 |            5.5 |
| Nuclear programme            |         3   |           5.9 |    1.3 |      2   |       0.8 |               4.3 |        2.5 |            5.7 |
| Media and information        |         3.4 |           5.6 |    6.9 |      7.2 |       6.8 |               8.7 |        4.2 |            4.9 |

## Topic model (NMF, one document per thread)

Share of each window's comments in threads whose strongest topic is this one. Topics are numbered, not named: name them from their words.

|   topic | top_words                                                                                |   june_2025 |   feb_2026 |
|--------:|:-----------------------------------------------------------------------------------------|------------:|-----------:|
|       1 | jews, palestinians, jewish, palestinian, palestine, hamas, genocide, gaza, arabs, muslim |        12.9 |        3.3 |
|       2 | oil, prices, strait, gas, hormuz, price, market, economy, energy, china                  |         2.4 |       15.1 |
|       3 | democrats, congress, dems, republicans, vote, republican, democrat, voting, gop, senate  |         9.1 |       13.3 |
|       4 | uranium, enriched, iaea, enrichment, program, nukes, facilities, nuke, fordow, bunker    |        23.2 |        1.6 |
|       5 | school, civilians, schools, civilian, children, girls, target, hit, targets, hospitals   |         2.9 |        6.4 |
|       6 | ukraine, china, region, allies, europe, nato, nukes, syria, ally, saudi                  |        14.7 |       13.1 |
|       7 | epstein, maga, putin, donald, files, taco, orange, prize, peace, idiot                   |        18.4 |       25.3 |
|       8 | air, drones, drone, missiles, systems, aircraft, missile, range, defenses, planes        |        10.8 |        8.3 |
|       9 | ships, ship, navy, warship, vessel, naval, vessels, boats, sunk, waters                  |         0.2 |        4.9 |
|      10 | khamenei, irgc, pahlavi, islamic, freedom, shah, giphy, gif, leader, reza                |         5.4 |        8.7 |

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
