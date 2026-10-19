# Player name sources

Downloaded on 2026-10-19 from the U.S. Census Bureau's [1990 name files](https://www.census.gov/topics/population/genealogy/data/1990_census/1990_census_namefiles.html).

| Bundled file | Original download | Selection |
| --- | --- | --- |
| `first_names.txt` | https://www2.census.gov/topics/genealogy/1990surnames/dist.male.first | All 1,219 entries from the male first-name file |
| `last_names.txt` | https://www2.census.gov/topics/genealogy/1990surnames/dist.all.last | First 5,000 distinct surnames in source frequency-rank order |

These Census Bureau datasets are U.S. federal government data, in the public domain in the United States. See the [U.S. Copyright Office's description of government works](https://www.copyright.gov/history/copyright-exhibit/lifecycle/).

Conversion: split each source row on whitespace, keep only the name (first column), apply Python `str.title()`, remove case-insensitive duplicates while preserving order, and write UTF-8 with one name per line and a final newline. Frequencies and ranks are not used by the game. Title casing is mechanical and does not infer internal capitals such as McDonald. The lists reflect the historical dataset, not a current football-player population.

The files provide 6,095,000 possible first/last combinations. They are bundled in git and loaded locally; the game never downloads names at startup or during simulation.

## Editing

Edit either text file directly, keeping one name per line. Blank lines and lines starting with `#` are ignored; duplicate spellings are ignored case-insensitively. Order matters for deterministic name generation. Restart the app after edits. Player display names can change after editing a pool; IDs, ratings, experience, and simulated production are independent of these lists.

## Download checksums (SHA-256)

- Original `dist.male.first`: `0a5078ef6effe3b483d15b0f7f95047662126c9bfb624ecd5e5b978fc0f2470b`
- Original `dist.all.last`: `b0e2b3743ccbad641ca48b344c24cdebcd1d9a1f76dc6dbf05986f2919f0b4e1`
- Bundled `first_names.txt`: `53c96f3cff6afe7cd71b8e088d758a75a2a90e04c9eacabe624fb33850bd0f57`
- Bundled `last_names.txt`: `18077958b7127bda60aa4b55d7cdae4e1733a3b13f4c39775919c2df0302616e`
