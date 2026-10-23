# Homebox compatibility

Companion is tested with Homebox **0.26.2 and 0.27.0**. Homebox API keys require
Homebox 0.26.0 or newer. Username/password login is also available, but does not
add support for older inventory APIs. See the [testing guide](../tests/README.md)
for the integration test matrix and commands.

## Parent containers and physical locations

On Homebox 0.27+, AI Chat can keep an item's parent container while setting a
separate physical location, or clear that override to follow the parent chain.

For integrations using the `update_item` tool:

- `location_override_id` sets a physical location without changing the parent.
- `clear_location_override` clears that override so the item follows its parent.
- `location_id` moves the item directly into a location.

Explicit overrides require a recognized Homebox version of 0.27.0 or newer.

## Typed custom field display in Homebox 0.27.0

Homebox 0.27.0 stores numeric and boolean custom fields correctly, but its item
detail page can display those values as blank. Companion preserves the stored
values. The [optional Homebox frontend patch](upstream/README.md) addresses this
display issue; it is separate from Companion.

## API key expiry

New API keys created by Homebox 0.27 default to a 30-day expiry when no expiry is
chosen. Existing non-expiring keys are not retroactively expired by an upgrade.
Check the expiry when creating a key and rotate it before that date. See the
[deployment guide](deployment.md#homebox-api-keys-and-access) for rotation steps.

## Asset IDs

Enter or scan a numeric Homebox ID, such as `032-303`, or leave it blank for
automatic assignment. Hyphens and leading zeros are accepted. IDs must fit
Homebox's signed 64-bit integer range. Zero is accepted by Homebox but represents
an unassigned ID. Invalid IDs must be corrected before analysis, confirmation or
submission.
