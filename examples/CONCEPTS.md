# Synthetic concept walkthrough

The [automated walkthrough](../tests/test_concepts.py) executes the Day 1–50 sequence in a new temporary folder: file interview/RFP sources, resolve or leave concept mentions ambiguous, attach precise evidence, form an open question, skip, explicitly confirm, flag a later conflict, and supersede explicitly. It also exercises novel transcript topics, stale review and source provenance. Run `python3 -B -m unittest discover -s tests -p test_concepts.py -v` from the vault. No data is written to the live catalog or knowledge folders.
