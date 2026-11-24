# TranslaDeo CLI

TranslaDeo CLI translates YouTube video titles and descriptions and uploads them as video localizations.

The CLI updates only `localizations` through the YouTube Data API. It does not modify `snippet`, the original metadata language, the audio language, or automatic dubbing.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

When upgrading an existing installation, remove the old distribution first:

```bash
python3 -m pip uninstall -y googletrans
python3 -m pip install -r requirements.txt
```

`googletrans` and `googletrans-curl` share the same Python import name and must
not be installed together.

1. Create a Google Cloud project.
2. Enable YouTube Data API v3.
3. Create OAuth credentials for a desktop app.
4. Download the JSON file and save it as `client_secret_youtube.json`.
5. Copy `video_ids.example.csv` to `video_ids.csv` and add your video IDs.

On the first run, the CLI opens a browser authorization flow and writes the
resulting OAuth token to `token.json`. Authorize with the Google account that
owns or can manage the YouTube channel containing the videos in `video_ids.csv`.

If authorization uses the wrong account, or the token becomes invalid, delete
`token.json` or leave it empty and run the CLI again. The app will start a new
authorization flow and recreate the token.

## Language Configuration

The target languages are defined in `config.py`.
If a language in the list matches the video's source language, it is skipped automatically.

`LANGUAGE_MAP` includes the 83 language codes returned by YouTube's
`i18nLanguages.list` endpoint when checked on November 24, 2026. All resolve to
supported Google Translate destinations. This API lists YouTube interface
languages; it is not an exhaustive catalog of every possible metadata or
subtitle language. Additional metadata targets can be configured separately.

YouTube regional codes are preserved in uploads. `en-GB`, `en-IN`, `es-419`,
`es-US`, and `fr-CA` use their base language for translation, so regional wording
is not guaranteed. `pt-PT` uses Google's European Portuguese destination.
`zh-HK` uses Traditional Chinese (`zh-tw`), as does `zh-TW`; this does not generate
Cantonese. `sr-Latn` uses Serbian with Cyrillic-to-Latin conversion. Simplified
and Traditional Chinese, Serbian scripts, and Portuguese variants remain
distinct when deciding which source language to skip.

Examples:

- source video `it`, target language `it`: skipped.
- source video `en-US`, target language `en`: skipped.
- `zh-CN` and `zh-TW` remain distinct.

## Translation Engine

TranslaDeo CLI uses
[`googletrans-curl`](https://pypi.org/project/googletrans-curl/), a free fork of
`googletrans` that still imports as `googletrans`. It translates through Google
Translate without requiring an API key or a Google Cloud billing account. The
CLI explicitly selects its curl transport, which uses browser-compatible TLS
and HTTP behavior to address the persistent 429 responses observed with the
original Python HTTP client. It remains an unofficial integration; Google can
still limit requests or change its endpoints.

Translation requests explicitly use the selected source language. Transient errors
are retried and logged instead of accepting the original text as a translation.
Requests are spaced at least two seconds apart. If Google returns HTTP 403 or 429,
the CLI stops the run immediately instead of repeating blocked requests for every
language and video. Empty results and results where the entire title and
description remain unchanged are rejected. This conservative check can also skip
metadata consisting only of names that legitimately stay the same in another
language. The translated title is logged for each successful language.

The YouTube Data API is still required for reading video metadata and uploading
localizations. The OAuth scope used by the CLI is
`https://www.googleapis.com/auth/youtube.force-ssl`.

## Source Language Selection

For each video, the CLI reads from YouTube:

- `defaultLanguage`
- `defaultAudioLanguage`

The behavior is:

- if both are present and match, that language is used;
- if only one is present, that language is used;
- if both are present but differ, the CLI asks the user which one to use;
- if both are missing, that video is skipped and the user is asked to fix the language in YouTube Studio.

The selected language is used only as the translation source and is never written back to YouTube.

## Commands

```bash
python3 main.py
python3 main.py --dry-run
python3 main.py --force-fetch
python3 main.py --force-retranslate
python3 main.py --dry-run --force-fetch --force-retranslate
python3 main.py --check-translation
python3 main.py --check-translation --all-languages
```

`--dry-run` prepares translations and shows how many localizations would be uploaded, but does not write anything to YouTube.

`--force-fetch` reads title, description, `defaultLanguage`, and `defaultAudioLanguage` from YouTube again, ignoring cached metadata.

`--force-retranslate` translates again even languages already marked as completed in the cache.

`--check-translation` translates a generic title and description into English
without reading video metadata, accessing YouTube, or changing the cache.
`--all-languages` extends this check to every configured target except the
Italian test source. The CLI reports failures explicitly. Exit code 0 means all
requested checks succeeded; exit code 1 means at least one failed or the service
blocked the run. Testing all targets takes several minutes because requests are
spaced apart.

## Google Translate Troubleshooting

`googletrans-curl` uses an unofficial endpoint, separate from the authenticated
YouTube Data API. HTTP 429 means Google is limiting translation requests; HTTP 403
means access is forbidden. These errors do not mean the YouTube OAuth token is
invalid, and changing YouTube credentials does not fix them.

Wait before retrying and use `--check-translation` to check availability with a
generic sentence. Google does not publish a guaranteed reset time for this
unofficial access, and spacing requests cannot lift an existing block.

A persistent 429 does not prove that this script exceeded a short-term quota.
Users have also reported persistent failures specific to the HTTP client used by
`googletrans`, while other clients continue working. See
[upstream issue #457](https://github.com/ssut/py-googletrans/issues/457).
This is a reported compatibility hypothesis, not a confirmed diagnosis for every
429 response. Waiting alone may not resolve it, and a reachable Google Translate
homepage does not establish that the translation endpoint works.

For a supported translation API, Google recommends
[Cloud Translation](https://docs.cloud.google.com/translate/docs/setup).
It requires enabling the API, configuring separate authentication, and enabling
billing, even when usage falls within its free allowance. The current CLI uses
`googletrans-curl`; switching to Cloud Translation requires a separate integration.

## Cache

The CLI stores its state in `translation_cache.json`.

The cache prevents translating the same videos again on every run. If you change title, description, or video language in YouTube Studio, use:

```bash
python3 main.py --force-fetch
```

If you want to regenerate all translations:

```bash
python3 main.py --force-retranslate
```

New translations are marked as completed only after a successful upload to
YouTube. Dry runs do not write to YouTube or mark translations as completed,
but they still exercise the fetch and translation flow and may cache source metadata.

If an earlier run uploaded Italian text under other languages, the old cache may
already mark those languages as completed. After updating the script, regenerate
and replace those localizations with:

```bash
python3 main.py --force-fetch --force-retranslate
```

Add `--dry-run` first to preview the translated titles without uploading.

## Authorization Troubleshooting

Before uploading, the CLI checks whether the authenticated YouTube account can
update the video's channel. If the account cannot update the video, the CLI stops
before translating and logs the video channel ID and the authenticated channel
IDs.

Common fixes:

- delete `token.json` and authorize again with the correct Google/YouTube account;
- make sure that account owns the channel or has sufficient channel management permissions;
- verify that YouTube Data API v3 is enabled in the Google Cloud project used by `client_secret_youtube.json`.

## What Gets Modified On YouTube

The CLI uploads only translated titles and descriptions to the video's localizations.

It does not modify:

- the original title and description;
- `defaultLanguage`;
- `defaultAudioLanguage`;
- audio;
- subtitles;
- automatic dubbing.

## Files You Must Not Publish

Never commit:

- `.env`
- `token.json`
- `client_secret*.json`
- `translation_cache.json`
- real CSV files containing private videos or channel data

## Support the Project

If you find this app useful and would like to support me, consider making a donation.

<p>
  <a href="https://paypal.me/maskennetwork" target="_blank">
    <img src="https://img.shields.io/badge/Donate-PayPal-blue?style=for-the-badge&logo=paypal" alt="Donate via PayPal">
  </a>
</p>

## License

This project is released under the [MIT License](LICENSE).
