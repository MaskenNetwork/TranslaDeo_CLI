# TubeLingo CLI

TubeLingo CLI translates YouTube video titles and descriptions and uploads them as video localizations.

The CLI updates only `localizations` through the YouTube Data API. It does not modify `snippet`, the original metadata language, the audio language, or automatic dubbing.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

1. Create a Google Cloud project.
2. Enable YouTube Data API v3.
3. Create OAuth credentials for a desktop app.
4. Download the JSON file and save it as `client_secret_youtube.json`.
5. Copy `video_ids.example.csv` to `video_ids.csv` and add your video IDs.

## Language Configuration

The target languages are defined in `config.py`.
If a language in the list matches the video's source language, it is skipped automatically.

Examples:

- source video `it`, target language `it`: skipped.
- source video `en-US`, target language `en`: skipped.
- `zh-CN` and `zh-TW` remain distinct.

## Translation Engine

TubeLingo CLI uses `googletrans`, a free Python library that translates text through Google Translate without requiring an API key or a Google Cloud billing account.

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
```

`--dry-run` prepares translations and shows how many localizations would be uploaded, but does not write anything to YouTube.

`--force-fetch` reads title, description, `defaultLanguage`, and `defaultAudioLanguage` from YouTube again, ignoring cached metadata.

`--force-retranslate` translates again even languages already marked as completed in the cache.

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
