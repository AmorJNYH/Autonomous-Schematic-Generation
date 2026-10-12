# Worst-case bounds and source conditions

Use this engineering guidance with [calculation-preflight.md](calculation-preflight.md).
It adds no calculation schema fields or automatic acceptance rule. The preflight
checks declared conditions and finite arithmetic; a replay of the same equation
and assumptions does not prove that its chosen point is an upper or lower bound.

## Bound the quantity over its actual domain

State the quantity being bounded, the allowed variable intervals and constraints,
and which direction is adverse. For a nonlinear quantity, evaluate every interval
endpoint, every admissible internal stationary point, and the constraint or
piecewise-model boundaries. Compare the resulting candidate extrema; do not
assume that the largest voltage or current produces the largest dissipation.
For example, a term proportional to `v * (supply - v)` can attain its maximum
inside the interval. This is a synthetic model example, not a device guarantee.

Retain dependencies: voltage, bias current, clamp voltage, temperature and a
state-dependent resistance may constrain one another. Independently selecting
each apparently adverse endpoint can form an impossible operating point, or
miss a feasible worse point. Analyze the joint feasible domain, including its
boundaries. In several dimensions, examine admissible interior stationary points
and lower-dimensional boundary extrema. If analytic or rigorous interval bounds
are unavailable, label a sampled sweep as sampling evidence, state its remaining
bound uncertainty, and keep the claim conditional. A coarse grid is not an
exhaustive extremum proof.

Keep the derivation and its source/model scope separate from arithmetic replay.
A second execution of the same conditional formula checks its arithmetic; it
does not independently justify monotonicity, the model, a derivative sign or
the claimed extremum. Use the existing DERIVED_BOUND derivation or located
external derivation to record the justified range and adverse direction.

## Match the source table to the operating conditions

Before using a limit, bind its exact part/variant, table row, revision, units and
all relevant test conditions to the actual design: voltage, temperature, current,
load, timing, measurement method and stated thermal/board conditions. A limit at
one supply voltage is not automatically a guarantee at another. A typical curve,
absolute maximum or value from a different row must not be substituted for the
required guaranteed operating limit.

Record each numeric limit used in a peripheral contract as a source-bound claim,
even when it is not an input to the arithmetic preflight. Include the exact
variant, revision, page/table/parameter row, units, MIN/TYP/MAX column, footnotes
and applicable operating conditions. Check the table headings and column position
against the actual source; text extraction can lose column alignment. A value in
TYP is an estimate, and a blank or dash in the needed limit column means that bound
remains unknown. Preserve the unknown in both the contract and dependent
calculations. Equation replay, a nominal budget or correct units cannot turn a
typical value into a maximum. For a load limit, distinguish the source-defined
quantity from additional board contributions that remain budgets or handoff
obligations. Retain independently established rating limits when a separate
stability or functional parameter remains unknown; that supported subset does not
close a criterion that also requires the unknown parameter. If the manufacturer
requires a nominal selection, preserve that requirement instead of inventing a
minimum effective value or a MIN/MAX requirement it did not specify.

Use interpolation as a guarantee only where the manufacturer explicitly permits
that method, within the specified conditions and endpoints, and for the stated
parameter. Record that permission and its scope. Otherwise, interpolation or
extrapolation is an engineering estimate with assumptions and a closure boundary;
it cannot be promoted to GUARANTEED or a supported bound by repeating its formula.
Even permitted voltage interpolation does not authorize temperature/current
interpolation or a different test condition.

Separate axes that the available evidence can bound from axes that remain truly
unknown. Complete the calculable bounds, disclose the remaining uncertainty, and
define its closure evidence. Missing guarantees on one axis do not excuse an
endpoint, stationary-point or source-condition contradiction on a known axis.
Conversely, a valid bound on one axis does not close all operating states or
temperatures. Apply the existing SUPPORTED/FAIL/CONDITIONAL claim rules; this
guidance creates no new automatic gate or historical downgrade.
