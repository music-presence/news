# music-presence/news

This repository hosts news that are shown in the Music Presence app.

## Contributing translations

You can contribute a translation of a news entry
by following these instructions:

1. Become a Music Presence translator first,
   by following the instructions
   [here](https://github.com/ungive/discord-music-presence/blob/master/documentation/translations.md).
2. Open [translate.codeberg.org/projects/music-presence/app-news](https://translate.codeberg.org/projects/music-presence/app-news/)
   which will give you an overview over what is left for translation.
   Once you were invited to the project, you should able to translate right away.

Before starting, keep the following in mind:
- Translations of the "banner", "title" and "short_title" keys
  are the most important
  (look for "Key" on the page of a translation string to find its key),
  as these texts are the first that users read,
  when they see a news popup.
  Translating these is quick and is more than enough.
  Please always translate them together, not just one of them.
- Make sure that the translated "short_title"
  is not longer than the original text.
  This stirng will be shown in the tray menu and has limited space.
- If you want to go the extra mile and translate the entire news text,
  then you are more than welcome to do so.
  Please try your best to match the tone of the original news entry.
  Also, please only translate if you are confident in your translating
  of continuous text (rather than individual words or sentences).
  If you feel like your translation would not match the original,
  it is okay to leave the news text untranslated.
- Thank you for contributing!

## Attribution of your translations

Since you are already a Music Presence translator,
your translations of the news will be attributed just the same way
as your app translations in the About window of the app.

## Maintenance

### Adding a new news entry

1. Lock the [Weblate project](https://translate.codeberg.org/projects/music-presence/app-news/).
2. Run `inv new`.
   Write the news entry (in English) until you are satisfied with it
3. Run `$ inv translations` to create translation files
   Run this task every time the news content is updated
4. Commit and push to GitHub, wait for the Weblate project to get the changes
5. Update the Weblate project with the news ID (replace `{id}`):
   1. Manage > Settings > Files: Set "File mask" to `news/{id}/translations/*.json`
   2. Manage > Settings > Files: Set "Screenshot file mask" to `news/0/banner/en/*.png`
   3. Put a screenshot of the news entry (within the app) on all strings,
      to help translators see where each string is located
6. Once everything looks good, unlock the Weblate project again

### Publishing a news entry

1. Lock the [Weblate project](https://translate.codeberg.org/projects/music-presence/app-news/)
2. Check for any missing or **outdated** translations.
   Due to using JSON for translation strings,
   outdated strings are not automatically detected.
   Either ask for correction or delete all outdated translations.
   Ideally, only open translations when the news text is set in stone
3. Run the `inv publish` task and lean back

## License

MIT License  
See [LICENSE](./LICENSE) for details.
