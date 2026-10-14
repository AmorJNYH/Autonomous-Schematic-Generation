# Evidence-bound discrete supply review

A rectifier, transformer, diode feed, or discrete pass stage may have only passive
symbol terminals. Keep their manufacturer pin types. A marker represents a
reviewed supply origin, not another component and not a proof of ratings.

Before declaring a source, inspect the source data and independent intent. Record
energy input, return path, polarity, conducting/startup states, disabled/fault
states and supply-load limits. Do not use this mechanism on feedback, threshold,
reference measurement, or other signal nets. A power role alone is not evidence.

`reviewed_circuit_supply` entries have exactly `net`, output `pin`, `refs`,
`reason`, `binding_sha256` and `evidence: {path, sha256, locator}`. `refs` lists
all relevant source-path components, at least two. The evidence is a readable
review document within the artifact root; its hash and exact locator must match.
Compute the binding with `schematic_layout.circuit_supply.binding(intent, refs)`
after the review is written. It binds component identities, values, fields,
complete participating net partitions and NC declarations. Do not refresh the
binding after an electrical change without reopening the review.

The board declares the net role as power or return. Put exactly one
`Sheet.power_flag()` at the reviewed output. `page_intents` carries the declaration
to its output-pin page. The full-board native audit checks original passive pin
connectivity and identities, absence of a conflicting native power output, marker
count, output net name, current source document and circuit binding. Missing,
stale, disconnected, signal or unreviewed declarations fail. The check does not
parse the engineering argument or prove it correct; SR must independently review
source semantics and operating limits. Report that distinction explicitly.

Use this only when supply semantics are actually known. A controller's uncertain
voltage margin can remain conditional; a path of unknown polarity or an unproved
energy source cannot be qualified. No broad waivers, ERC exclusions or fake
power-output pin types are allowed.
