---
name: percent_check
claim_type: percent_check
fields: [count, total, percent]
---
**percent_check** - percentages reported together with the count and the total they are based on,
e.g. "23 of 61 participants (37.7%) were female" or a table cell "45 (52.3%)" in a column headed n = 86.
Extract one claim per percentage where BOTH the numerator and the denominator are explicitly stated in the
paper. Do not compute or guess a missing count or total; skip weighted or model-estimated percentages.

- `count`: the numerator (number of cases), as a STRING exactly as printed
- `total`: the denominator the percentage refers to, as a STRING (the relevant subgroup n, not always the full N)
- `percent`: the percentage as a STRING exactly as printed, without the % sign, keeping trailing zeros (e.g. "37.70")
- `quote`: verbatim passage from the paper reporting the count and percentage

Example: `{"type": "percent_check", "count": "23", "total": "61", "percent": "37.7", "quote": "23 of 61 participants (37.7%) were female"}`
