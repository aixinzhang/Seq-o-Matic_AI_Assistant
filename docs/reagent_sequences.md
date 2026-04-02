# Reagent Sequence File Format

Reagent sequence files define the step-by-step fluidics protocols executed by the `FluidicSystem`. They are JSON files located in `code/reagent_sequence_file/`.

---

## File Format

Each file is a JSON array of step objects. Steps are executed sequentially from top to bottom.

```json
[
  {"volume": 1.5, "source": "1", "flow_rate": 1.5, "time": null, "temperature": null, "Solution name": "Incorporation Buffer", "device": "pump"},
  {"volume": 0, "source": null, "flow_rate": null, "time": 180, "temperature": null, "Solution name": "Heat Wait", "device": "heat_device"},
  {"volume": 4, "source": "2", "flow_rate": 1.5, "time": null, "temperature": null, "Solution name": "PBST", "device": "pump"},
  {"volume": 0, "source": null, "flow_rate": null, "time": 600, "temperature": null, "Solution name": "Incubation Wait", "device": "wait"},
  {"volume": 0, "source": "14", "flow_rate": null, "time": null, "temperature": null, "Solution name": "Empty End", "device": "stopper"}
]
```

---

## Step Fields

| Field | Type | Description |
|-------|------|-------------|
| `device` | string | **Required.** Step type: `"pump"`, `"heat_device"`, `"wait"`, or `"stopper"` |
| `volume` | float | Volume to pump in mL. Used by `"pump"` steps. Set to `0` for non-pump steps. |
| `source` | string or null | Reagent selector address (as string, e.g., `"1"`, `"2"`). Maps to `Fluidics_Reagent_Components.json`. Used by `"pump"` steps. |
| `flow_rate` | float or null | Pump flow rate in mL/min. Used by `"pump"` steps. Typical value: `1.5`. |
| `time` | int or null | Duration in seconds. Used by `"heat_device"` and `"wait"` steps. |
| `temperature` | float or null | Target temperature. Currently unused (reserved for future use). |
| `Solution name` | string | Human-readable description of this step (shown in log). |

---

## Device Types

### `"pump"` -- Reagent Delivery

Selects a reagent source via the Elveflow multiplexer and pumps the specified volume at the given flow rate.

**Required fields:** `volume`, `source`, `flow_rate`

```json
{"volume": 3.0, "source": "2", "flow_rate": 1.5, "time": null, "temperature": null, "Solution name": "PBST", "device": "pump"}
```

The `source` value corresponds to an `address` in `Fluidics_Reagent_Components.json`:
- `"1"` = incorporation buffer
- `"2"` = PBST
- `"3"` = Iodoacetamide Blocker
- ... (see `Fluidics_Reagent_Components.json` for full mapping)

### `"heat_device"` -- Heated Incubation

Activates all configured heating stages for the specified duration. Temperature is controlled by a fixed voltage; duration is monitored per-stage.

**Required fields:** `time`

```json
{"volume": 0, "source": null, "flow_rate": null, "time": 180, "temperature": null, "Solution name": "IRM heat Wait", "device": "heat_device"}
```

### `"wait"` -- Room-Temperature Incubation

Pauses the sequence for the specified duration without pumping or heating. Used for incubation steps at ambient temperature.

**Required fields:** `time`

```json
{"volume": 0, "source": null, "flow_rate": null, "time": 600, "temperature": null, "Solution name": "DAPI incubation Wait", "device": "wait"}
```

### `"stopper"` -- End of Sequence

Marks the end of a fluidics sequence. Must be the last step. The `source` field is typically set to `"14"` (the "END" address on the selector).

```json
{"volume": 0, "source": "14", "flow_rate": null, "time": null, "temperature": null, "Solution name": "Empty End", "device": "stopper"}
```

---

## Available Protocol Files

### Standard Protocols (root of `reagent_sequence_file/`)

| File | Description |
|------|-------------|
| `Fluidics_sequence_bcseq01.json` | Barcode sequencing cycle 1 (first cycle, includes primer + blocker) |
| `Fluidics_sequence_bcseq02+.json` | Barcode sequencing cycles 2+ (subsequent cycles, simplified) |
| `Fluidics_sequence_geneseq01.json` | Gene sequencing cycle 1 |
| `Fluidics_sequence_geneseq02+.json` | Gene sequencing cycles 2+ |
| `Fluidics_sequence_HYB.json` | Hybridization protocol (oligo probe delivery + FISH wash) |
| `Fluidics_sequence_HYB_rehyb.json` | Re-hybridization protocol |
| `Fluidics_sequence_add_bc_primer.json` | Add barcode primer only |
| `Fluidics_sequence_add_bc_primer_rehyb.json` | Add barcode primer for re-hybridization |
| `Fluidics_sequence_add_gene_primer.json` | Add gene primer only |
| `Fluidics_sequence_add_gene_primer_rehyb.json` | Add gene primer for re-hybridization |
| `Fluidics_sequence_strip.json` | Strip existing probes/signals |
| `Fluidics_sequence_fill_all.json` | Prime all lines (fill each source with 1 mL) |
| `Fluidics_sequence_flush_all.json` | Flush/wash all lines |
| `Fluidics_sequence_user_defined01.json` | User-customizable protocol template |

### Protocol Variants (subdirectories)

| Directory | Description |
|-----------|-------------|
| `original_sequence/` | Backup copies of the default protocols |
| `2IRM_and_2CRM/` | Modified protocols using double IRM and CRM steps |
| `750um gasket/` | Modified protocols for 750um gasket configuration (different volumes) |

---

## Creating a Custom Protocol

1. Copy an existing protocol file as a template.
2. Modify the steps as needed, following the field format above.
3. Ensure the last step is a `"stopper"` device.
4. Ensure all `source` values correspond to valid addresses in `Fluidics_Reagent_Components.json`.
5. Save to `reagent_sequence_file/` with the naming pattern `Fluidics_sequence_<name>.json`.
6. Register the protocol name in `FluidicSystem.find_protocol()` if it should be auto-loaded by process name.

### Example: Simple Wash Protocol

```json
[
  {"volume": 5, "source": "2", "flow_rate": 1.5, "time": null, "temperature": null, "Solution name": "PBST Wash", "device": "pump"},
  {"volume": 0, "source": null, "flow_rate": null, "time": 120, "temperature": null, "Solution name": "Wash Incubation", "device": "wait"},
  {"volume": 3, "source": "2", "flow_rate": 1.5, "time": null, "temperature": null, "Solution name": "PBST Rinse", "device": "pump"},
  {"volume": 0, "source": "14", "flow_rate": null, "time": null, "temperature": null, "Solution name": "End", "device": "stopper"}
]
```

---

## Known Issues

- In `Fluidics_sequence_bcseq01.json`, lines 8 and 11 contain duplicate `"device": "pump"` keys in the same JSON object. JSON parsers typically use the last value, so this doesn't cause runtime errors, but it should be cleaned up.
