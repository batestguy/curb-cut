# disability-access-charts

Accessible charts for Python, built by and for disabled data users. The goal: every chart ships with alt-text that is checked against its data, an accessibility audit you can run in CI, and a data-table fallback.

**Status: early (0.0.x).** This release contains only the WCAG 2.2 contrast checks; the chart API follows. Part of the [Curb Cut](https://github.com/batestguy/curb-cut) project.

```python
from disability_access_charts import contrast_ratio, passes_text, passes_non_text

contrast_ratio("#0072b2", "#ffffff")  # 5.19
passes_text("#767676", "#ffffff")  # True  (SC 1.4.3, 4.5:1)
passes_non_text("#f0e442", "#ffffff")  # False (SC 1.4.11, 3:1)
```

MIT licensed.
