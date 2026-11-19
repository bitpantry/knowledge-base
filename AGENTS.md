# Agent entry point

For routine vault operations, follow the [operating instructions shipped to vaults](packaging/vault-AGENTS.md.in). Do not load or search `docs/` for routine cataloging, retrieval, or extension use.

Before designing or changing the core, packaging, or any shared architecture rule, read the canonical [Design Principles](docs/DESIGN-PRINCIPLES.md), then the relevant [architecture notes](docs/README.md) and core contract. Confirm the user explicitly authorized the architecture change. If routine work reveals a gap, explain it and wait for approval rather than adding a new convention or dependency in a live vault.

Read relevant operating instructions and tests, review the precise diff, and validate in system temporary storage rather than in a working projects folder.
