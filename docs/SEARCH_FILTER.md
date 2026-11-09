# Search filter

All project searches go through one function in `ui/index.html`:

```js
searchProjects(filter, options)
applyFilter(filter)
```

`searchProjects` returns matching projects in order. `applyFilter` also displays the result: chips, search bar, and project list.

The search bar, chips, quick filters, and saved filters all produce the same JSON object. A future local AI model only needs to generate that object and pass it to `applyFilter`.

Every field is optional. A project must satisfy **all** supplied fields. `cleanFilter` ignores unknown fields and incorrect types, so a malformed filter does not break the list.

## Fields

| Field | Type | Meaning | Search bar examples |
|---|---|---|---|
| `text` | string | Free words, all required: name, folder, title, artist, plugins, tags, notes, sample names | `dark lead`, `"dark lead"` |
| `bpm` | `{min, max}` | Rounded BPM | `bpm:140`, `bpm:130-150`, `bpm>130` |
| `hours` | `{min, max}` | Work time in hours | `time>2h`, `time:1h-3h`, `time<30m` |
| `sizeMb` | `{min, max}` | Size in MB: the FLP plus found samples | `size>500mb`, `size<1gb` |
| `year` | `{min, max}` | Creation year | `year:2023`, `year:2020-2023` |
| `version` | string | FL version, including a prefix | `version:21`, `version:21.2` |
| `plugins` | string list | Plugins, all required | `plugin:serum`, `plugin:"pro-q 3"` |
| `samples` | string list | Part of a sample filename | `sample:kick` |
| `tags` | string list | Tags assigned in the app | `tag:sold` |
| `folder` | string | Part of the folder path | `folder:trap` |
| `key` | string | Musical key saved by FL or inferred from the name | `key:am`, `key:"a minor"` |
| `missing` | boolean | Has missing files | `missing:yes` |
| `unread` | boolean | Could not read the project | `unread:yes` |
| `exported` | boolean | Has an associated WAV, always a possible match | `export:no` |
| `favorite` | boolean | Favorite project | `favorites:yes` |
| `otherPc` | boolean | At least one missing sample belongs to another Windows user or a disconnected drive | `otherpc:yes` |
| `forgottenMonths` | number | Not modified for at least this many months | `forgotten:yes` (6 months), `forgotten:12` |
| `almostDoneHours` | number | At least this many work hours and no associated WAV | `almostdone:yes` (3 hours), `almostdone:5` |
| `sort` | `{by, reverse}` | Order; `by`: `hours`, `mod`, `created`, `bpm`, `size`, `name`, `st` | JSON only |

The bar also accepts the original Italian aliases: `tempo`, `peso`, `anno`, `versione`, `cartella`, `tonalita`, `mancanti`, `nonletti`, `preferiti`, `dimenticati`, `altropc`, and `quasifiniti`.

## Example

“Trap beats from 2023 around 140 BPM, using Serum, with more than two hours of work, that I left unfinished”:

```json
{
  "text": "trap",
  "year": { "min": 2023, "max": 2023 },
  "bpm": { "min": 135, "max": 145 },
  "plugins": ["serum"],
  "hours": { "min": 2 },
  "forgottenMonths": 6
}
```

## Behavior

- **Case and accents** do not matter. `serum` finds `Serum x64`; `citta` finds `Città`.
- **Typing mistakes:** words are searched exactly first. Similar words are used only if no project contains the original word: one edit for words up to six letters, two for seven or more, and no tolerance below four letters. The count above the list states which similar words were used.
- **Identical copies** count as one project, represented by the newest copy. If a copy matches, its representative appears. Use `options.allCopies` to return every copy.
- **`searchProjects` options:** `allCopies` (boolean), and `sort` (the same structure as above, used when the filter has no sort order).
