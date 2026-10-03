# Pre-outcome contract execution revision

Preserve the original eight-candidate batch and its failed metadata/execution audit: on 2018-11-13 it requires a missing 6EZ9 bar. No strategy outcome or selection metric has been evaluated. Single-bar volume ranking across every expiry can jump to a sparsely traded far maturity after a block trade; forward-only rolling then strands the series. This is an execution-policy failure, not evidence against or for the economic signals.

Replace only the shared contract eligibility/ranking rule for a separately recorded revised eight-trial batch:

- Keep the fixed six roots, whole contracts, received-definition availability, exact raw-symbol/instrument-ID/expiry identity and 40-calendar-day expiry exclusion.
- Require every eligible contract to have actual observed bars on all of the previous 20 common portfolio weekdays available at the decision clock. Its mean traded volume over those 20 bars must be at least 100 contracts. This supports at least one whole contract at the existing 1% participation cap; each actual proposed trade must still pass the original capacity test.
- Among eligible maturities, retain only the nearest two expiries. Choose the higher trailing-20-bar mean volume; retain an eligible incumbent on a tie. Roll only forward. A previously eligible incumbent outside the nearest two must roll to a later eligible maturity; never fall back to an earlier maturity. If no forward eligible maturity exists, the experiment fails explicitly.
- CL/GC carry formation uses the nearest two maturities passing the same causal liquidity/expiry rule. No later prices, interpolated quotes, guessed expiry, threshold search or silent universe/date removal.

Use the same rule for all candidates, controls, neighbours and clock stress. Record the original failed attempt and all eight revised trials in the ledger, clearly separating infrastructure revisions from evaluated alpha variants. Keep the signal menus, economic hypotheses, costs, capital/risk rules, calendar/split dates, training-only selection and locked final holdout unchanged. Parameters 20 and 100 are fixed execution safeguards, not values selected for performance. Commit this revision before evaluating any strategy outcome.
