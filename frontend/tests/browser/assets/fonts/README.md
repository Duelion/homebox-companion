# Offline browser fonts

Latin variable-font subsets used by `src/app.html`, retrieved 2026-10-01 from Google Fonts:

- Inter v20: https://fonts.gstatic.com/s/inter/v20/UcC73FwrK3iLTeHuS_nVMrMxCp50SjIa1ZL7.woff2
- Outfit v15: https://fonts.gstatic.com/s/outfit/v15/QGYvz_MVcBeNP4NJtEtq.woff2
- JetBrains Mono v24: https://fonts.gstatic.com/s/jetbrainsmono/v24/tDbV2o-flEEny0FZhsfKu5WU4xD7OwE.woff2

Each font is distributed under its adjacent SIL Open Font License, sourced from
`https://github.com/google/fonts/tree/main/ofl/<family>/OFL.txt`.
Fixtures serve these bytes as embedded CSS so tests never depend on live font servers.
Update deliberately with reviewed Linux screenshots when the app's typography changes.
