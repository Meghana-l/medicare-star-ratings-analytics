# Reference files

Two optional CSVs make the real-data run exact. Both come from the CMS Technical Notes PDF for the rating year.

**measure_meta.csv** (written as a template the first time you load real data)

| column | meaning |
|---|---|
| measure_id | e.g. C01, D08 |
| name | measure name |
| source | HEDIS, CAHPS, HOS, Admin or Part D |
| part | C or D |
| weight | Star Ratings weight from the Technical Notes |
| higher_is_better | 1, or 0 when a lower score is better |
| definition, numerator, denominator, exclusions | plain-language spec text shown on the "Measure specs" tab |

**cutpoints_YYYY.csv** (one file per rating year; add earlier years to get the trend chart)

```
measure_id,t2,t3,t4,t5
C01,62,72,80,87
```

`t2..t5` are the score thresholds for 2 to 5 stars. Higher-is-better measures: a score at or above `t_k` earns `k` stars.
Lower-is-better measures: a score below `t_k` earns `k` stars, so the numbers fall as `k` rises.

Without a cut point file, the loader estimates thresholds from CMS's published stars and the site shows a warning.
