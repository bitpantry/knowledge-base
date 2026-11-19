# Tool Loans

**Use for:** a shared shed, maker space, or volunteer group lending equipment. This is a synthetic example, not a live inventory or approval system.

**Owner and audience:** The local vault operator owns the extension. Use fictitious examples or data approved for this vault's audience. Store borrower aliases, not contact details.

**Module:** [Lending](modules/lending/README.md).

**Model:** [Loan](modules/lending/MODEL.md). Lending is the sole writer; one immutable loan ID per checkout. This extension manages only checkout/return state, not inventory ownership or permission to lend.

**Dependencies:** The core Markdown vault layout and Python 3.9+ standard library. No package install, registry, network, or compatibility step. The core does not load or execute this extension automatically.

## Start here

Copy this entire `tool-loans/` folder into another copy of the vault's `extensions/` folder. Open this file and follow [first use](modules/lending/README.md#first-use). No core edits or other copied files are required. Before copying, inspect any existing folder at the destination and do not overwrite another vault's records.
