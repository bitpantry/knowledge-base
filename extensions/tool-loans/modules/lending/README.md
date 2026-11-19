# Lending

This module records a checkout, lists what's out, and closes the loan when the tool returns. [Loan model](MODEL.md).

## First use

From the vault root, run this read-only command. It should show no loans in a fresh copy.

    python3 -B extensions/tool-loans/modules/lending/loans.py list --open

To try a fictional checkout in a **clean test vault**, use:

    python3 -B extensions/tool-loans/modules/lending/loans.py checkout loan-demo-01 "Cordless drill" "Volunteer Finch" 2026-11-19
    python3 -B extensions/tool-loans/modules/lending/loans.py list --open
    python3 -B extensions/tool-loans/modules/lending/loans.py return loan-demo-01 2026-11-20
    python3 -B extensions/tool-loans/modules/lending/loans.py check

Records live under `records/` next to this file and can be read in Obsidian. The CLI only writes inside that directory. The enclosing vault's core files and records are not changed. The example has no sharing, notifications, or outside actions. Do not treat this ledger as evidence of permission to lend a tool.
