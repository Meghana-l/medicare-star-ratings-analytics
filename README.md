# Medicare Advantage Star Ratings: Policy Analytics

Live: https://medicare-star-ratings-analytics-kappa.vercel.app/

An interactive tool that shows how Medicare Advantage health plans earn their 1 to 5 star rating, and what it would take to earn the next star.

**Why it matters:** the Centers for Medicare & Medicaid Services (CMS) rates every Medicare Advantage plan each year. Higher stars bring bonus payments and more members, so plans track exactly which measures are closest to the next star. This project rebuilds that calculation in the open, from CMS's public data.

## What you can do

- **Overview:** see how plans are spread across the star ratings.
- **Plan scorecard:** pick a plan and see every measure, its score and its stars.
- **Gap to next star:** see which measures are closest to the next cut point and which carry the most weight.
- **Distributions and trends:** see where plans score on a measure, where the cut points sit, and how they moved over the years.
- **Measure specs:** read what each measure counts, where its data comes from (HEDIS, CAHPS, HOS, administrative, Part D) and how much it is worth.
- **Data checks:** see the automated quality checks, including whether the stars rebuilt here match the ones CMS published.

## How the stars work

1. Each plan has a **score** on each measure, for example the share of diabetic members whose blood sugar is controlled.
2. CMS sets **cut points** for each measure. A score above a cut point earns that star. For a few measures, like complaints, a lower score is better.
3. A plan's **overall rating** is the weighted average of its measure stars.

## Built with

- **Python** to load, clean and check the data
- **SQL** (SQLite) to calculate the stars and the gap to the next star
- **pytest** for tests of the calculation
- **HTML, CSS and JavaScript** with Chart.js for the site, with no server needed

## Run it locally

```bash
pip install -r pipeline/requirements.txt
python -m pipeline.build --demo
python -m pytest -q
cd web && python -m http.server 8000
```

## Good to know

- The plans and scores in the live site are synthetic samples that demonstrate the tool. The calculation is the one CMS publishes, and it reads CMS's public Star Ratings tables.
- The overall rating here is a weighted average of measure stars. CMS also applies a reward factor and other adjustments, so overall ratings can differ slightly. Measure-level stars are the exact comparison.
- It works at the plan level, using published scores. It does not use member-level data.
- Independent project using public CMS data. Not affiliated with or endorsed by CMS.
