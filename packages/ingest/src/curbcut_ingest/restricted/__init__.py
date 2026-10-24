"""Restricted-zone harmonisation: licensed microdata to person-level Parquet.

Everything here reads files under the git-ignored ``data/restricted/`` and writes only to
``data/restricted/derived/``. Nothing in this package prints a data value: logs carry
variable names, row counts and match rates, with any count under 30 shown as "<30".
"""
