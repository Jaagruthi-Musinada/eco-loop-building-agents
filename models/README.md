# Building models

Put your baseline `.idf` here as `baseline.idf`.

Fastest path for the hackathon: EnergyPlus ships example files under
`<ENERGYPLUS_DIR>/ExampleFiles/`. `5ZoneAirCooled.idf` is a good starting
point — it has multiple zones with thermostats you can expose as actuators.

`baseline_modified.idf` will be written automatically by the loop if you add
IDF-editing (via `eppy`) on top of the runtime setpoint control — useful if
your ECMs include structural changes (e.g. adding a new schedule) rather than
just actuator value changes.
