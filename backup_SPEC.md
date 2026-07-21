# Temperature-Dependent Auxiliary Heating — Specification

Status: **Design locked, pending implementation approval**
Branch: `dev-hvac-update#1`
Scope: OpenStudio-HPXML workflow (`measures/`, `building.py`, `project.yaml`)

---

## 1. Problem

We want to model a building whose heating is served by **two systems** — the
**primary** (HPXML **system 1**) and the **auxiliary** (HPXML **system 2**) —
such that the auxiliary only contributes **when it gets cold enough**, producing
a realistic **two-slope energy signature** (energy vs. outdoor temperature) with
an emergent **change point**.

> **Terminology (fuel-agnostic, general).** Throughout this spec:
> - **system 1 = primary = base-load** (the `heating_system_*` inputs; EnergyPlus
>   heating sequence 1 — served first).
> - **system 2 = auxiliary = peaking** (the `heating_system_2_*` inputs;
>   EnergyPlus heating sequence 2 — served second).
>
> The assignment is **by system number, not by fuel.** Any mention of a
> "boiler" or "electric resistance" is only an **illustrative example**; the
> mechanism applies to whatever fuels/types are placed in system 1 and system 2
> via the building-stock CSV.

A naive fixed split (e.g. "system 2 always serves 20% of the load") produces a
**single-slope** signature for each system and therefore **cannot** reproduce the
change-point / heating-slope behavior seen in real dual-system homes. We need
the auxiliary (system 2) contribution to be **zero above a switchover
temperature** and to **grow as temperature drops**.

### Constraint (hard)
- **Do not modify the HPXML schema.** The solution must work with the existing
  HPXML inputs and the existing OpenStudio-HPXML measures.

---

## 2. Physical model — capacity cascade

Instead of prescribing fixed temperature bins, the change point **emerges** from
a **base-load + peaking (lead-lag) capacity cascade**:

- The **primary (system 1)** is deliberately sized to a **fraction** of the
  design load: `C_primary = f_primary · Q_design`.
- The **auxiliary (system 2)** is sized to the remainder:
  `C_aux = (1 − f_primary) · Q_design`.
- At runtime the **primary (system 1) runs first** every timestep (base load).
  It follows the heating load until it **saturates** at its capacity, then
  **plateaus**.
- The **auxiliary (system 2) picks up only the residual** the primary cannot
  supply.

### Emergent change point
Because the load is (approximately) linear between the balance point `T_base` and
the design temperature `T_design`, the primary saturates at:

```
T_start = T_base − f_primary · (T_base − T_design)
```

- Above `T_start`: auxiliary = 0, primary follows load.
- Below `T_start`: primary = constant plateau (`C_primary`), auxiliary = load − C_primary.
- At `T_design`: auxiliary = `(1 − f_primary) · Q_design`, primary = `f_primary · Q_design`.

Because `f_primary + f_aux = 1`, combined capacity always equals `Q_design`, so
there are **no unmet hours** down to the design temperature. The plateau comes
from the **primary alone** saturating, not from the system running short.

### Energy signature (axes: T increases left→right; T_design at left, T_base at right)

```
Energy
  |
  |  *                         Heating load  (falls to 0 at T_base)
  |   *
  |    *
  |  ___*___________           primary plateau (C_primary)
  |  :   *          '''---___
  |  :    *                 '''---___
  |  : o   *                         '''---___
  |  :   o  *                                 '''---___
  |__:_____o_*_____________________________________'''___ T
  T_design  T_start                                 T_base
   (cold, left)                                    (warm, right)

   *  Heating load          (straight line, high at T_design → 0 at T_base)
   o  Auxiliary (system 2)  0 at T_start, grows toward the cold (∥ to load)
   _  Primary   (system 1)  follows load down to T_start, then plateaus
```

Reading left→right (cold → warm), matching your axis:
- At **T_base** (right): load = 0, both systems off.
- Between **T_base** and **T_start**: primary follows the load, auxiliary = 0.
- At **T_start**: primary saturates at `C_primary`; auxiliary just begins.
- Between **T_start** and **T_design**: primary plateaus flat; auxiliary grows
  toward the cold but is still **less than** `(1 − f_primary)·Q_design`.
- At **T_design** (left): auxiliary = `(1 − f_primary)·Q_design`,
  primary = `f_primary·Q_design`.

Stacking identity at every temperature: **primary + auxiliary = heating load.**
The auxiliary line is the heating-load line shifted straight down by the plateau
height, i.e. **parallel to the load line**.

This is the textbook **base-load + peaking / lead-lag** behavior of real dual
HVAC systems (HP + backup, lead/lag boilers, base furnace + aux).

---

## 3. Interface — fraction is the only input

Separation of concerns:

- **External to the tool (user's responsibility):** choose `T_base`, `T_start`,
  `T_design` and invert the change-point equation to pick the design fraction:

  ```
  f_primary = (T_base − T_start) / (T_base − T_design)
  ```

  where `T_design` is the EPW 99% heating design drybulb and `T_base` is a
  nominal balance point. All change-point placement intelligence lives in the
  user's external energy-signature analysis.

- **Inside the tool (deterministic):** given the **fraction** `f_primary` per
  building, the tool:
  1. writes it as the HPXML **design fraction** → ACCA sizing splits the capacity
     (`C_primary = f_primary · Q_design`, `C_aux = (1 − f_primary) · Q_design`);
  2. after sizing, **overrides both sequential heating-fraction schedules to 1.0**
     → produces the cascade dispatch.

The simulator stays dumb: *given fraction `f`, produce the base-load/peaking
cascade.* No knowledge of `T_start`/`T_base`/`T_design` is needed inside the tool.

---

## 4. The core technical tension (and its resolution)

`fraction_heat_load_served` in HPXML does **double duty**:

1. **Sizing** — `hvac_sizing.rb` (`get_fractions_load_served`, ~L5213) scales
   each system's `Heat_Capacity` by its `fraction_heat_load_served`.
2. **Dispatch** — `hvac.rb` (`calc_sequential_load_fractions`, ~L87 / ~L5098)
   converts the fraction into per-day **sequential load fraction schedules**
   that tell EnergyPlus what share of the remaining zone load each system takes.

**Problem:** if we set the sequential fraction to 1.0 to get the cascade, it
would *also* resize the primary to 100% of design — erasing the change point.

**Resolution (Option A):** decouple the two roles in time.
- Let the **HPXML design fractions drive SIZING** (untouched → capacity split).
- **After Step 4 sizing**, override only the **sequential heating-fraction
  SCHEDULES** to 1.0 on the two heating objects. Sizing is already done, so the
  capacities remain split; only dispatch changes to lead-lag.

No EMS, no schema change.

---

## 5. Constraints & considerations

- **No HPXML schema change** (hard constraint).
- **No EMS.** The existing EMS in `hvac.rb` (`set_sequential_load_fractions`,
  ~L5144) only fires for `is_heat_pump_backup_system == true`; our standalone
  secondary system does not trigger it, so there is **no EMS collision**.
- **Sum-to-1 coverage.** `f_primary + f_aux = 1` guarantees full capacity and
  **no unmet hours** to `T_design`. (The schematron `EPvalidator.xml` requires
  `sum(FractionHeatLoadServed) == 1`, which we satisfy.)
- **Targeting the right objects.** Sequential fraction schedules have generic
  names ("Sequential Fraction Schedule"), so equipment must be identified via
  the `HPXML_ID` **additionalProperties** tag that OpenStudio-HPXML attaches to
  each object. The **system 1 → primary** and **system 2 → auxiliary** mapping is
  resolved by matching `HPXML_ID` to the HPXML heating-system identifiers
  (`HeatingSystem1` = system 1 = base-load, `HeatingSystem2` = system 2 =
  peaking), **not** by fuel/type and **not** by the generic schedule names.
  Verified in the generated model: EnergyPlus heating sequence 1 = system 1,
  sequence 2 = system 2 under `SequentialLoad`.
- **Soft knee.** The real change point at `T_start` is a **rounded corner**, not
  sharp, because primary runtime saturates gradually over the coldest part-load
  hours. Expected and acceptable for a signature study.
- **`T_base` is approximate.** The true balance point emerges from UA, internal
  gains, solar and setpoint. Analytical `T_start` placement is therefore
  approximate; the user owns this trade-off externally (optionally pinned by a
  one-shot calibration run). Out of scope for the tool.

### Scope (v1)
- **Single conditioned zone.**
- **One primary + one auxiliary** heating system per building:
  **system 1** (`heating_system_*`) = primary/base-load, **system 2**
  (`heating_system_2_*`) = auxiliary/peaking. The role is assigned **by system
  number, not by fuel** — whatever type/fuel is placed in system 1 is the
  primary, and whatever is in system 2 is the auxiliary.
- **Standalone secondary system**, NOT a heat-pump backup. HP-backup case is
  **deferred** until this approach is validated.
- **Pure capacity cascade** — the original fixed temperature bins
  (0 / −5 / −15 °C) are **dropped**; the cascade supersedes them.

---

## 6. Implementation outline (for approval — not yet built)

1. **New OpenStudio Model measure** (Ruby), e.g. `SetSequentialHeatingCascade`,
   placed in `measures/`. It:
   - loads the OpenStudio model produced by Step 4 (post-sizing);
   - finds the two heating objects via `HPXML_ID` additionalProperties
     (`HeatingSystem1` = primary/system 1, `HeatingSystem2` = auxiliary/system 2);
   - replaces each object's **sequential heating fraction schedule** with a
     constant `1.0` schedule (via `setSequentialHeatingFractionSchedule`);
   - leaves capacities (already sized from the HPXML design fractions) untouched.

2. **Wire into `building.py`** as **Step 4b**, immediately after Step 4
   (`HPXMLtoOpenStudio`, ~L256) and before Step 5 (`ReportSimulationOutput`,
   ~L264), so it operates on the sized model prior to the run.

3. **`project.yaml`** — add a toggle/arg to enable the cascade measure. The
   per-building **fraction** continues to flow through the existing
   `heating_system` / `heating_system_2` fraction inputs (from the building
   stock CSV), so **no schema change** is required.

4. **Validation** — run the 3-building sample, then use
   `analyze_hvac_loads.py` to confirm the primary plateau and the auxiliary
   pickup at the expected `T_start` on the energy signature.

### Enabling / disabling (reversibility)

The feature is **opt-in and fully reversible** because Step 4b is purely
additive — it only mutates the model when enabled.

- **Run a "current implementation" (default) case:** set the `project.yaml`
  toggle to `false` (or omit it). Step 4b is **skipped**, the model keeps the
  stock sequential heating-fraction schedules generated by OpenStudio-HPXML, and
  the simulation behaves exactly as today (fractions do their normal double duty
  — sizing *and* proportional dispatch). No inputs change.
- **Run a cascade case:** set the toggle to `true`. Step 4b overrides the two
  sequential heating-fraction schedules to `1.0` on the sized model.
- **Remove the feature permanently:** delete the measure folder, its Step 4b
  call in `building.py`, and the flag in `project.yaml`. Nothing else depends on
  it — no schema, no EMS, no capacity edits, no other code paths.

---

## 7. Open items deferred (not in v1)
- Heat-pump-backup variant (EMS interaction to be re-examined).
- Multi-zone / multiple-unit buildings.
- Automated `T_base` calibration pass.
