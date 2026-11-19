# Loan model

Owner: Lending module under Tool Loans. The record's authority is the checkout/return confirmed by the local operator. The core catalog is not the source of truth for these fields. This minimal example has no references to external artifacts.

- **ID**: stable `loan-` prefix plus lowercase letters, digits and hyphens.
- **Tool**: descriptive name.
- **Borrower**: approved alias, not an address or contact detail.
- **Checked out**: date in ISO format.
- **Returned**: optional ISO date, not before checkout.
- **Status**: derived from the return date.

The module script is the writer for this format. One Markdown record per loan. No deletion or notification commands are included.
