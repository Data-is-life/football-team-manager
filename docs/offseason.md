# Simplified offseason

[Quick start](../QUICKSTART.md) · [Project overview](../README.md)

New careers use rules 42 and save version 43. Existing careers retain their
original rules and recorded offseason sequence.

**Season ends → Draft → Sign your own players → Free agency → Trade → Start season**

## Own-player signing

After the six-round draft, sign or release your expiring veterans and drafted
rookies in Roster. Active contracts continue automatically. Rookie draft-slot
pay is reserved against the cap until you sign or release the player; signing
replaces the hold, rather than adding the same salary twice. A signed contract
is fully guaranteed. Declining a rookie leaves no guaranteed charge.

Finish this stage after resolving those decisions and satisfying the cap. CPU teams make their own retention and
renewal decisions before the market opens. There are no new contracts after
free agency closes, so consider positional needs before finishing the market.

## Fixed-price free agency

Choose a player to sign, or end free agency. There is no pass action, wave
counter, automatic market deadline, or wave discount. Prices use normal demand
and the existing destination premium, remaining fixed within that offseason.
CPU teams can sign after each user signing; ending the market resolves their
remaining needs at those same prices. A signing must fit the cap and the reserved cost of filling minimum roster
requirements. The roster may temporarily exceed 38 players; finalize cuts
after the market closes, before finishing trading and starting the season.

The pool consists of current-class undrafted rookies, players declined or
released by teams, and eligible unsigned carryovers. Emergency minimum-roster
replacements are handled separately and never offered as free agents.

A player first available in the Year 2 market may remain available in Year 3.
If still unsigned, that player leaves the pool before Year 4. Signing removes
their free-agent entry record; a later release starts a new unsigned spell.
Aging and retirement still apply to unsigned players.

## Trading and starting the season

Ending free agency opens Trades. Resolve the 60% payroll minimum, salary cap,
31–38-player roster and position requirements before finishing. The existing
payroll-minimum adjustment remains available for review and confirmation.

Trading retains the deterministic 1-for-1 valuation policy, whole-contract
transfers, CPU depth protections, and restrictions on current-year rookies and
new free-agent signings. See the [trade valuation reference](rules-reference.md#trading-period-new-careers-rules-41).

Training camp is removed. Finishing trading starts the new season and runs
aging, development and rookie reassessment exactly once. Rookie outcomes use
seeded per-player probabilities: **25% boom, 25% bust, 50% regular development**.
Actual counts vary by draft class. The existing outcome magnitudes and position
curves remain in place. Assessments include UDFAs; signing and trade previews do
not reveal or reroll outcomes. Reloads reconstruct the same decisions and results.
