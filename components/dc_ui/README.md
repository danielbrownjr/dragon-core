# dc_ui

`dc_ui` packages the dependency-free Dragon-family browser SPA as a reproducible
gzip asset. `dc_portal` serves it and owns the shared provisioning/recovery
transport. Product firmware keeps ownership of authentication, API v2, and
hardware policy.

The SPA discovers product identity and supported surfaces from `GET /api/v2/info`.
The additive family descriptor is:

```json
{
  "capabilities": ["power_on", "auto", "drying"],
  "ui": {
    "schema": 1,
    "product": "dragonbreath",
    "display_name": "DragonBreath"
  }
}
```

DragonVent selects its dedicated airflow surface with an additive descriptor:

```json
{
  "capabilities": ["vent_manual", "vent_auto", "source_status", "polling"],
  "ui": {
    "schema": 1,
    "product": "dragonvent",
    "display_name": "DragonVent"
  }
}
```

DragonStatus selects the family-owned status-light surface the same way:

```json
{
  "capabilities": ["source_status", "lighting", "polling"],
  "ui": {
    "schema": 1,
    "product": "dragonstatus",
    "display_name": "DragonStatus"
  }
}
```

The DragonStatus surface uses the family’s ember-orange accent (`#F97316`) and
renders its printer, Wi-Fi, and lighting readiness state from `/api/v2/state`.
Product firmware owns those state values; the SPA owns their presentation.

Its lighting screen edits `/api/v2/lighting` with the same two-knob shape as
DragonVent: `mode` chooses where the colour comes from (per-printer-state palette
or one fixed colour) and `effect` chooses the animation, where `0` means the
product's own per-state policy. Alongside those it round-trips a colour per
printer state (`unbound`, `idle`, `downloading`, `preparing`, `printing`,
`paused`, `complete`, `error`), `brightness`, `speed`, `reverse`, and the
`complete_hold_min` / `standby_min` policy timers. Every field is optional on
POST, so firmware may implement a subset.

That surface uses the same responsive shell and appearance controls as
DragonBreath, but has vent-specific state, manual open/close controls, and the
automatic bed-temperature policy. It does not reinterpret vent motion as heater
state. DragonVent consumers provide `vent`, `printer`, `policy`, and `wifi` objects
in `/api/v2/state`, plus the compact `/api/v2/command` and `/api/v2/settings`
adapters documented by their product firmware.

`capabilities` gates optional screens. An older firmware response without the array
keeps every current screen visible, preserving compatibility with already-shipped
DragonBreath API v2 implementations. Schema `1` is the current family descriptor;
an unknown schema is ignored so the static product identity and complete UI remain
available.

Although route handlers stay product-local, the shared client owns the browser side
of the Dragon API v2 wire contract. A consumer must provide `/api/v2/info`,
`/api/v2/state` and the command/settings routes used by its selected surface. SSE at
`/api/v2/events` is optional: the client attempts it first and falls back to
serialized polling when it is unavailable. Multi-device discovery/grouping and any
future WebSocket transport are separate follow-ons.

Consuming builds require a host `gzip`; CMake uses `gzip -9 -n` to generate the
reproducible embedded asset.

The SPA renders `dc_portal`'s versioned `/api/v1/provisioning` schema in a common
setup overlay. It opens automatically in AP mode, so the same SPA is the normal UI
on the LAN and on the captive setup network. Product-specific fields are described
by firmware callbacks rather than compiled into another server-rendered page.

Product setup sections may opt into immediate, conditional controls without changing
the existing explicit-Save default. The optional schema additions are:

- field `type: "toggle"` for a boolean value;
- field `auto_submit: true` to POST only that field on change;
- field `hint_by_value` to select small help text from the current value;
- field `disabled_when` with `{ "field": ..., "equals": ... }`;
- field `confirm_on_change` with a requested `value`, optional dependent `when`,
  product-supplied text, and button labels;
- section `hide_action: true` when every mutation in that section is immediate.

For example:

```json
{
  "title": "Optional feature",
  "hide_action": true,
  "fields": [
    {
      "key": "feature_enabled",
      "label": "Feature",
      "type": "toggle",
      "value": false,
      "auto_submit": true,
      "hint_by_value": {
        "false": "Standard behavior is active.",
        "true": "Optional behavior is active."
      },
      "confirm_on_change": {
        "value": true,
        "when": { "field": "remembered_preference", "equals": true },
        "title": "Enable feature?",
        "body": "Product-provided acknowledgement text.",
        "cancel_label": "Cancel",
        "confirm_label": "Enable"
      }
    },
    {
      "key": "remembered_preference",
      "label": "Remembered preference",
      "type": "toggle",
      "value": true,
      "auto_submit": true,
      "disabled_when": { "field": "feature_enabled", "equals": true },
      "hint": "Used whenever the optional feature is disabled."
    }
  ]
}
```

Toggle mutations are sent as JSON booleans. A guarded toggle is restored to its
committed value before the acknowledgement opens; Cancel sends no request, while
confirmation applies the requested value. A rejected request restores the committed
value and surfaces the firmware error. All labels, policy conditions, and messages
remain product-owned.

## Firmware update check (optional, opt-in)

If a product advertises a release repository in `GET /api/v2/info`, the Settings /
setup surface offers an update check:

```json
{ "update": { "repo": "owner/name", "asset_prefix": "yourproduct-" } }
```

When present, the SPA makes **one** request per page load to
`https://api.github.com/repos/<repo>/releases/latest` — but only on installed builds
(a stable or `-rc`/`-beta` version). Local/dev builds (`-dirty`, or a `git describe`
`-g<hash>` suffix) skip the request entirely, so constant dev reloads can't exhaust the
shared per-IP GitHub rate limit for real users behind the same NAT. When it does run and
the latest stable tag is newer than the running firmware, it shows the version, the
expected asset SHA-256, and a download link. Release-asset bytes are not CORS-readable, so it notifies and links —
the user downloads then uploads via the file picker; it never auto-flashes.

This is the one place the device's admin UI reaches the public internet. It is
**opt-in** (absent `update.repo`, nothing happens — e.g. on an isolated IoT VLAN it
silently does nothing), sends no device data, and is bounded to one request per load.
Firmware without the descriptor is unaffected.
