# Contributing translations

Ubuntu Start uses gettext. English text in the application is the source. The shared template, `po/ubuntu-start.pot`, is the canonical list of messages for every translation catalog in this directory. The current catalog is Swedish (`po/sv.po`). You can improve it or contribute another language.

## Language status

| Language | Code | Status |
| --- | --- | --- |
| English (source) | `en` | Complete |
| Swedish | `sv` | Complete |

Every catalog listed in `po/LINGUAS` must be complete, non-fuzzy and pass CI. Add a language there only when its catalog is ready for users.

## Before translating

- Read the whole screen or guide where a message appears. A short label can mean different things in different places.
- Keep the meaning, tone and level of detail. Use clear language that makes sense to a new Ubuntu Desktop user.
- Keep product and proper names such as Ubuntu, App Center, Orca and WiFi Analyzer unchanged.
- Preserve placeholders exactly, including their braces and spelling. For example, `{free}`, `{total}` and `{percent}` are filled in by the application.
- Do not translate gettext metadata, message IDs or source-code references. Do not edit the POT template by hand; regenerate it from the English source.
- Leave a message fuzzy only while it still needs review. Remove the fuzzy marker after checking the finished translation.

## Update the shared template and catalogs

Keep `po/ubuntu-start.pot` in version control. It is used by `msgmerge` to bring existing `.po` catalogs up to date, and by `msginit` to start catalogs for new languages. When English text changes or a new source string is added, regenerate the template from both the Python app and its desktop entry, then merge it into each catalog.

Run these commands from the repository root:

```sh
xgettext --from-code=UTF-8 --language=Python --keyword=_ --keyword=_n:1,2 \
  --package-name="Ubuntu Start" --package-version=0.3.48 \
  --copyright-holder="Ubuntu Start contributors" \
  --msgid-bugs-address=https://github.com/yeager/ubuntu-start/issues \
  --output=po/ubuntu-start.pot src/ubuntu_start.py
xgettext --from-code=UTF-8 --language=Desktop --join-existing \
  --package-name="Ubuntu Start" --package-version=0.3.48 \
  --copyright-holder="Ubuntu Start contributors" \
  --msgid-bugs-address=https://github.com/yeager/ubuntu-start/issues \
  --output=po/ubuntu-start.pot data/se.danielnylander.UbuntuStart.desktop
msgmerge --update --backup=none --no-fuzzy-matching \
  po/sv.po po/ubuntu-start.pot
```

If the project version changes, update `--package-version` to match `meson.build`. Repeat the `msgmerge` command for every `.po` file listed in `po/LINGUAS`. Edit only the `msgstr` values in a translation catalog. Keep each translation next to its `msgid`, and check that placeholders and punctuation still match the sentence.

## Add another language

1. Create a catalog from the shared template, replacing `fr` with the language code:

   ```sh
   msginit --input=po/ubuntu-start.pot --locale=fr --output-file=po/fr.po
   ```

2. Translate each `msgstr`. Keep the generated language metadata and plural forms for that locale.
3. Add the language code to `po/LINGUAS`, one code per line.
4. Run the checks below and include the new catalog and `LINGUAS` change in your pull request.

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
