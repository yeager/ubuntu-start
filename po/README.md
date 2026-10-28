# Contributing translations

Ubuntu Start uses gettext. English text in the application is the source; translated catalogs live in this directory. Swedish (`sv`) is the current translation. You can help improve Swedish or contribute a new language.

## Before translating

- Read the whole screen or guide where a message appears. A short label can mean different things in different places.
- Keep the meaning, tone and level of detail. Use clear language that makes sense to a new Ubuntu Desktop user.
- Keep product and proper names such as Ubuntu, App Center, Orca and WiFi Analyzer unchanged.
- Preserve placeholders exactly, including their braces and spelling. For example, `{free}`, `{total}` and `{percent}` are filled in by the application.
- Do not translate gettext metadata, message IDs, source-code references or the POT template.
- Leave a message fuzzy only while it still needs review. Remove the fuzzy marker after checking the finished translation.

## Update a translation

From the repository root, regenerate the English message template and merge it into the Swedish catalog:

```sh
xgettext --from-code=UTF-8 --language=Python --keyword=_ \
  --output=po/ubuntu-start.pot src/ubuntu_start.py
xgettext --from-code=UTF-8 --language=Desktop --join-existing \
  --output=po/ubuntu-start.pot data/se.nylander.UbuntuStart.desktop
msgmerge --update --backup=none --no-fuzzy-matching \
  po/sv.po po/ubuntu-start.pot
```

Edit the `msgstr` values in `po/sv.po`. Keep each translation next to its `msgid`, and check that placeholders and punctuation still match the sentence. Do not edit `po/ubuntu-start.pot` by hand; it is generated from the English source.

## Add another language

1. Copy `po/sv.po` to a catalog named with the new language code, such as `po/fr.po`.
2. Update its language metadata and translate every `msgstr`.
3. Add the language code to `po/LINGUAS`, one code per line.
4. Run the checks below and include the catalog and `LINGUAS` change in your pull request.

## Check your work

Run these commands from the repository root:

```sh
python3 scripts/check-translations.py
msgfmt --check --check-format --statistics po/sv.po -o /tmp/ubuntu-start-sv.mo
test -z "$(msgattrib --untranslated --no-obsolete po/sv.po)"
test -z "$(msgattrib --only-fuzzy --no-obsolete po/sv.po)"
```

For a new language, replace `sv` in the last three commands with that language's code. The translation checker confirms that catalogs match the committed template and that the template matches current Python and desktop-entry strings. CI runs the same coverage and catalog checks.

## Open a translation pull request

Explain which language and screens you changed, note any wording that needs product context, and list the checks you ran. Include screenshots when they help reviewers judge a visible text change, and make sure they contain no personal information. See the repository's [contribution guide](../CONTRIBUTING.md) for the general pull request and review process.
