# Homebox 0.27.0 typed custom fields

Homebox 0.27.0 stores numeric and boolean custom fields correctly, but its item
detail page displays only `textValue`. Consequently, typed values such as numeric
`0` and boolean `false` appear blank. Companion updates preserve these typed values.

[`homebox-0.27.0-typed-custom-fields.patch`](homebox-0.27.0-typed-custom-fields.patch)
is a separate Homebox frontend fix against v0.27.0, commit
`bae3fb4e9b84672e4e64da15e57a14217aea7c13`. It formats the active text, numeric, or
boolean value, uses localized Yes/No labels, and keeps text links working. It does
not modify stored fields. Twelve focused regression cases cover zero, false, true,
null, text, links, and data preservation.

Apply it in a clean Homebox checkout at that commit:

```sh
git apply --check /path/to/homebox-0.27.0-typed-custom-fields.patch
git apply /path/to/homebox-0.27.0-typed-custom-fields.patch
```

Build Homebox with its official Dockerfile to include the frontend in the Go
binary. This patch is provided separately; it is not an upstream release and is
not included in the Companion image. No conversion of typed fields to text or
historical data migration is needed.
