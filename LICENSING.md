# Licensing and distribution

Updated 2026-10-22. This project uses the Volatility Software License 1.0 (VSL)
for its Volatility integration and preserves the MIT grant for original project
material. The project-authored software and associated documentation identified
below are expressly offered under **both VSL 1.0 and MIT**. This supplies the VSL
grant for covered Additions without withdrawing existing MIT permissions.

The integrated application is distributed in compliance with VSL. The additional
MIT grant allows independent reuse of original material; it does not remove the
VSL obligations that arise from distributing a Volatility wrapper or other covered
Addition. Volatility itself is not offered under MIT by this project.

No advance permission or reply from the Volatility Foundation is required to use
the existing VSL on its stated terms. A separate agreement is relevant only if a
distributor wants different terms, such as withholding source for covered Additions.

## License texts and scope

- [VSL 1.0](licenses/LicenseRef-Volatility-Software-License-1.0.txt): verbatim from
  [Volatility 3 v2.28.2](https://github.com/volatilityfoundation/volatility3/blob/v2.28.2/LICENSE.txt).
- [MIT](licenses/MIT.txt): the original project notice and grant, retained unchanged.
- [Third-party notices](THIRD_PARTY_NOTICES.md): dependencies, plugins, reference
  sources and artwork retain their own rights and notices.

| Component | License treatment |
| --- | --- |
| Original `src/volatility_workbench/**` software, including `app.py`, `guarded_scoped.py`, `volshell.py`, orchestration, providers and HTML/CSS/JavaScript UI code | Expressly available under VSL 1.0, with the existing MIT grant also retained. This includes the whole original application code so VSL compliance does not depend on treating a separate process or UI as exempt. |
| Original `packaging/**`, scripts, tests, templates, documentation and project configuration | Both VSL 1.0 and MIT, excluding separately attributed third-party material. |
| Pinned `volatility-mcp` | Its VSL offer and retained MIT grant; preserve the core's licenses and publish the corresponding pinned source. |
| Bundled Volatility 3 and official plugins | Their upstream VSL and notices; not relicensed by this project. |
| Dependencies, downloaded plugins and third-party artwork | Their respective rights and notices; excluded from the project-wide grant. |

## Distributing a build

1. Keep both project license texts, original copyright notices and applicable
   dependency/plugin notices in the wheel, app or other distribution.
2. When providing a covered Addition to others, publish its complete corresponding
   project source under VSL in the preferred form for modification through a freely
   accessible source-distribution service. Include scripts, configuration and
   project-authored resources needed to modify the distributed software. Use the
   exact release revision and the pinned core revision, not just an unrelated or
   newer checkout. A private repository or source supplied only on request does
   not meet VSL's public-source condition.
3. Identify the published source locations and revisions with the binary. The
   canonical repositories are
   [volatility-mcp](https://github.com/NoCoolUserName/volatility-mcp) and
   [volatility-workbench](https://github.com/NoCoolUserName/volatility-workbench).
   Verify that recipients can access the corresponding revision without signing
   in; if a development repository is private, publish a reviewed source archive
   or public source repository when releasing. Listing a private URL is not
   publication. Keep private evidence, credentials and case data out of source.
4. Preserve the exact-version upstream licenses. The project grants cover original
   project contributions only. Downloaded or vendored third-party code is governed
   by its own terms, including source/notice obligations where applicable.

These are distribution steps, not a requirement to stop private local development
or await an approval email. This change records license grants; it does not publish
an application release or change repository visibility.

## Theme artwork

The two Fallout 76 bezel PNGs were edited from supplied game references. Their
redistribution rights are separate from Volatility's software license; neither the
MIT nor VSL grant authorizes third-party artwork. See [THEMES.md](docs/THEMES.md)
for the asset-by-asset provenance and public-build options. The current private
appearance and theme catalog are unchanged. Clear the affected art or prepare an
authorized public-build alternative before distributing those assets.

## Optional plugins and historical references

The XP compatibility implementation is included in the project's VSL offer. Its
historical structure/layout references and attribution remain in the source and
third-party notices; this grant does not relicense Volatility 2 or copied upstream
material. Community plugins retain the licenses in their pinned sources. The
existing base-bundle allowlist is unchanged. Sources without a redistribution grant
remain outside distributed bundles; GPL/AGPL components require their own applicable
source and notice compliance. Downloading a plugin locally is distinct from
redistributing it in a binary package.

The dependency inventory and collected notices record component provenance.
Refresh them when the actual dependencies change; the October 18 inventory is a
historical dependency snapshot, not the current project license grant.
