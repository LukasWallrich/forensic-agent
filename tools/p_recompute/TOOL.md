---
name: p_recompute
claim_type: p_recompute
fields: [test, statistic, p]
---
**p_recompute** - null-hypothesis tests reported with a test statistic, degrees of freedom and a p-value,
e.g. "t(28) = 2.20, p = .036", "F(2, 57) = 4.11, p < .05", "χ²(1) = 3.84, p = .05", "z = 1.96, p = .05",
"r(48) = .31, p = .03". Extract one claim per complete test; skip tests without a p-value ("ns") or statistic.

- `test`: one of "t", "F", "chi2", "z", "r"
- `statistic`: the test statistic as a STRING exactly as printed, including sign and trailing zeros (e.g. "2.20")
- `p`: the p-value as a STRING exactly as printed, without the comparator (e.g. ".036", ".001")
- `p_comparator` (optional): "=", "<" or ">" (default "=")
- `df1`: degrees of freedom, as a STRING - required for t, F (numerator), chi2 and r (df = N - 2); omit for z
- `df2`: denominator degrees of freedom, as a STRING - required for F only
- `one_tailed` (optional): true only if the paper explicitly says the test is one-tailed/one-sided
- `quote`: verbatim passage from the paper containing the test result

Example: `{"type": "p_recompute", "test": "F", "statistic": "4.11", "df1": "2", "df2": "57", "p": ".05", "p_comparator": "<", "quote": "F(2, 57) = 4.11, p < .05"}`
