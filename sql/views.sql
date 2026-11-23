-- Star calculation expressed in SQL: raw score -> measure star via cut points.

-- 1) Measure-level stars rebuilt from raw scores and the cut points.
CREATE VIEW calc AS
SELECT
  s.contract_id,
  s.measure_id,
  s.score,
  s.cms_star,
  CASE
    WHEN s.score IS NULL OR c.measure_id IS NULL THEN NULL
    WHEN m.higher_is_better = 1 THEN
      CASE WHEN s.score >= c.t5 THEN 5
           WHEN s.score >= c.t4 THEN 4
           WHEN s.score >= c.t3 THEN 3
           WHEN s.score >= c.t2 THEN 2
           ELSE 1 END
    ELSE
      CASE WHEN s.score < c.t5 THEN 5
           WHEN s.score < c.t4 THEN 4
           WHEN s.score < c.t3 THEN 3
           WHEN s.score < c.t2 THEN 2
           ELSE 1 END
  END AS calc_star
FROM scores s
JOIN measures m ON m.measure_id = s.measure_id
LEFT JOIN cutpoints c
       ON c.measure_id = s.measure_id
      AND c.year = (SELECT CAST(value AS INTEGER) FROM meta WHERE key = 'year');

-- 2) Distance to the next star, for every measure below 5 stars.
--    next_cut = the cut point for (current star + 1); norm_gap = gap as a share of the 2-to-5 star span.
CREATE VIEW gap_to_next AS
SELECT
  k.contract_id,
  k.measure_id,
  k.score,
  k.cms_star,
  k.calc_star,
  m.weight,
  CASE k.calc_star WHEN 1 THEN c.t2 WHEN 2 THEN c.t3 WHEN 3 THEN c.t4 WHEN 4 THEN c.t5 END AS next_cut,
  CASE WHEN k.calc_star IS NULL OR k.calc_star >= 5 THEN NULL
       WHEN m.higher_is_better = 1
         THEN (CASE k.calc_star WHEN 1 THEN c.t2 WHEN 2 THEN c.t3 WHEN 3 THEN c.t4 WHEN 4 THEN c.t5 END) - k.score
       ELSE k.score - (CASE k.calc_star WHEN 1 THEN c.t2 WHEN 2 THEN c.t3 WHEN 3 THEN c.t4 WHEN 4 THEN c.t5 END)
  END AS gap,
  ABS(c.t5 - c.t2) AS band_span
FROM calc k
JOIN measures m ON m.measure_id = k.measure_id
LEFT JOIN cutpoints c
       ON c.measure_id = k.measure_id
      AND c.year = (SELECT CAST(value AS INTEGER) FROM meta WHERE key = 'year');

-- 3) Weighted average of rebuilt measure stars (before CMS reward factor / adjustments),
--    rounded to the nearest half star.
CREATE VIEW overall_calc AS
SELECT
  k.contract_id,
  SUM(k.calc_star * m.weight) * 1.0 / SUM(m.weight)       AS wavg,
  ROUND(SUM(k.calc_star * m.weight) * 2.0 / SUM(m.weight)) / 2.0 AS calc_overall,
  COUNT(*)                                                 AS n_rated
FROM calc k
JOIN measures m ON m.measure_id = k.measure_id
WHERE k.calc_star IS NOT NULL
GROUP BY k.contract_id;
