# hass-pontos (SYR SafeTech+) leverage suggestions for Safetec Water

This note reflects a review of `hass-pontos-master.zip` and now focuses only on **SYR SafeTech+** patterns that can be reused by `safetec_water`.

## What to leverage first (high impact)

1. **Use SafeTech+ bulk endpoint (`/trio/get/all`) first**
   - In `hass_pontos` SafeTech+ config, `URL_ALL_DATA` uses one bulk call (`http://{ip}:5333/trio/get/all`).
   - For Safetec Water, prefer bulk-read + parser, then fallback to per-endpoint calls only when needed.

2. **Adopt config-driven sensor mapping from SafeTech+**
   - `conf_safetech.py` defines SafeTech+ `SENSOR_DETAILS` with endpoint key, units, scale, code dictionaries, and attributes.
   - We should move hardcoded endpoint handling in `sensor.py` to a mapping table to simplify maintenance and extendability.

3. **Reuse SafeTech+ retry/backoff strategy**
   - `hass_pontos` `fetch_data` retries failed requests with bounded attempts and delay.
   - Add bounded retry/backoff for Safetec fetches to improve resilience on temporary network/device hiccups.

4. **Apply options reliably without manual restart**
   - `hass_pontos` updates fetch configuration (IP/fetch interval) through options flow and coordinator behavior.
   - Safetec Water should use robust options-change reload behavior for host/port/scan interval changes.

5. **Expand SafeTech+ code decoding centrally**
   - SafeTech+ includes explicit dictionaries for alarm, warning, notification, valve, Wi-Fi state, and microleakage schedule/status.
   - We should centralize these code maps and expose readable values consistently.

## Additional findings from SYR public API docs (SafeTech+ relevant)

6. **Treat payload content as authoritative for errors**
   - The API documentation states that errors can be returned in payload content and not only via HTTP status codes.
   - We should explicitly parse and classify payload-level error markers to avoid false "success" updates.

7. **Support feature variability by firmware/product matrix**
   - The docs note that not every device supports every telemetry/status value.
   - We should make sensor creation/availability conditional by returned keys and avoid hard-failing missing values.

8. **Preserve command semantics for control paths**
   - The docs show command-specific nuances (for example, some set endpoints without value payloads and dedicated Wi-Fi state commands).
   - If control entities are added later, endpoint templates should be declarative to prevent malformed requests.

## Additional SafeTech+ improvements worth copying

9. **Profile and diagnostic attribute mapping**
   - SafeTech+ maps profile entities and related diagnostic attributes declaratively.
   - This pattern can simplify firmware/serial/network/profile-related attributes in Safetec Water.

10. **Fixture-based testing from real SafeTech+ payloads**
   - `hass-pontos` includes test payload JSON files and a local serving helper.
   - Add SafeTech+-based fixtures for parser/conversion/hourly-consumption tests to prevent regressions.

11. **CI quality gates used by hass-pontos**
   - `hass-pontos` includes validation/hassfest/version workflows.
   - Mirror these checks for better HACS reliability.


## Rate-limit / lockout duration (documentation check)

- In the reviewed SafeTech+ API documentation, we did **not** find a documented lockout duration (seconds/minutes) after too many calls.
- The docs describe payload-level errors and command-range errors, but no explicit 429-style quota window or cooldown timer.
- Recommendation: add an empirical stress test against a local device to determine practical thresholds and recovery time, then codify a conservative request budget in the integration.

## Caution: what to adapt (not copy blindly)

- `hass_pontos` is multi-device and multi-platform (sensor/button/valve/select/time/switch/profile).
  - Safetec Water should stay focused on required scope unless control entities are intentionally added.
- Keep Home Assistant-native config-entry reload semantics as source of truth.

## Suggested implementation order

1. Add SafeTech+ `/trio/get/all` probe + parser + fallback path.
2. Move sensor definitions to a SafeTech+-focused mapping table (units/scales/code dictionaries/attributes).
3. Add payload-level error classification + graceful handling of missing/unsupported keys.
4. Add bounded retry/backoff for fetch operations.
5. Add options update listener and guaranteed reload path.
6. Add fixtures/tests for parsing + conversions + hourly consumption behavior.
7. Add CI checks (hassfest/validation/version gate).
