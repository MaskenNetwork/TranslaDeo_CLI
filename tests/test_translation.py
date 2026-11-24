import copy
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import httpx

from config import LANGUAGE_MAP, Settings
from main import is_same_language, main, process_video
from translator_client import MetadataTranslator, TranslationServiceBlocked, translation_language_code


class TranslationTests(unittest.TestCase):
    def setUp(self):
        self.translator = MetadataTranslator(Settings(
            max_retries=2, retry_wait_seconds=0, translation_request_interval_seconds=0,
        ))
        self.translator.loop.run_until_complete(self.translator.translator.client.aclose())
        self.requests = []
        self.handler = lambda request: self.response(request)
        self.translator.translator.client = httpx.AsyncClient(
            transport=httpx.MockTransport(self.handle_request),
        )
        self.addCleanup(self.translator.close)

    def handle_request(self, request):
        self.requests.append(request)
        return self.handler(request)

    @staticmethod
    def response(request, translated=None):
        original = request.url.params["q"]
        if translated is None:
            translated = {"Titolo italiano": "English title", "Descrizione italiana": "English description"}[original]
        return httpx.Response(200, json=[[[translated, original]], None, "it"], request=request)

    def test_http_error_never_returns_original_as_success(self):
        for status in (403, 429):
            with self.subTest(status=status):
                self.requests.clear()
                self.handler = lambda request: httpx.Response(status, request=request)
                with self.assertRaises(TranslationServiceBlocked):
                    self.translator.translate("Titolo italiano", "Descrizione italiana", "en", "it")
                self.assertEqual(len(self.requests), 1)

    def test_description_failure_rejects_the_entire_localization(self):
        def handler(request):
            if request.url.params["q"] == "Descrizione italiana":
                return httpx.Response(429, request=request)
            return self.response(request)

        self.handler = handler
        with self.assertRaises(TranslationServiceBlocked):
            self.translator.translate("Titolo italiano", "Descrizione italiana", "en", "it")

    def test_transient_server_error_is_retried(self):
        def handler(request):
            if len(self.requests) == 1:
                return httpx.Response(503, request=request)
            return self.response(request)

        self.handler = handler
        with self.assertLogs(level="ERROR"):
            result = self.translator.translate("Titolo italiano", "", "en", "it")
        self.assertEqual(result["title"], "English title")
        self.assertEqual(len(self.requests), 2)

    def test_success_uses_explicit_source_language(self):
        result = self.translator.translate("Titolo italiano", "Descrizione italiana", "en", "it")
        self.assertEqual(result, {"title": "English title", "description": "English description"})
        self.assertTrue(all(request.url.params["sl"] == "it" for request in self.requests))
        self.assertTrue(all(request.url.params["tl"] == "en" for request in self.requests))

    def test_source_region_and_chinese_aliases(self):
        for source, expected in (("it-IT", "it"), ("zh-TW", "zh-tw")):
            with self.subTest(source=source):
                self.requests.clear()
                self.translator.translate("Titolo italiano", "", "zh-CN", source)
                self.assertEqual(self.requests[0].url.params["sl"], expected)
                self.assertEqual(self.requests[0].url.params["tl"], "zh-cn")

    def test_all_configured_languages_are_supported_by_translation_engine(self):
        from googletrans import LANGUAGES

        unsupported = [code for code in LANGUAGE_MAP if translation_language_code(code) not in LANGUAGES]
        self.assertEqual(unsupported, [])

    def test_regional_target_aliases(self):
        for target, expected in (
            ("en-GB", "en"), ("en-IN", "en"), ("es-419", "es"),
            ("es-US", "es"), ("fr-CA", "fr"), ("pt-PT", "pt-pt"),
            ("zh-HK", "zh-tw"), ("sr-Latn", "sr"),
        ):
            with self.subTest(target=target):
                self.requests.clear()
                result = self.translator.translate("Titolo italiano", "", target, "it")
                self.assertIsNotNone(result)
                self.assertEqual(self.requests[0].url.params["tl"], expected)

    def test_serbian_latin_target_has_latin_title_and_description(self):
        self.handler = lambda request: self.response(
            request, "Љубав и Његош" if request.url.params["q"] == "Titolo italiano" else "ЉУБАВ И ЏЕЗ",
        )
        result = self.translator.translate("Titolo italiano", "Descrizione italiana", "sr-Latn", "it")
        self.assertEqual(result, {"title": "Ljubav i Njegoš", "description": "LJUBAV I DŽEZ"})

    def test_source_language_matching_preserves_script_and_portuguese_variants(self):
        self.assertTrue(is_same_language("en-US", "en-GB"))
        self.assertTrue(is_same_language("ZH-tw", "zh-TW"))
        self.assertFalse(is_same_language("zh-CN", "zh-TW"))
        self.assertFalse(is_same_language("sr", "sr-Latn"))
        self.assertFalse(is_same_language("pt", "pt-PT"))

    def test_unchanged_metadata_is_rejected_even_with_http_200(self):
        self.handler = lambda request: self.response(request, request.url.params["q"])
        with self.assertLogs(level="ERROR"):
            result = self.translator.translate("Titolo italiano", "Descrizione italiana", "en", "it")
        self.assertIsNone(result)

    def test_empty_translation_is_rejected(self):
        self.handler = lambda request: self.response(request, "")
        with self.assertLogs(level="ERROR"):
            result = self.translator.translate("Titolo italiano", "", "en", "it")
        self.assertIsNone(result)

    def test_empty_description_does_not_need_a_translation_request(self):
        result = self.translator.translate("Titolo italiano", "", "en", "it")
        self.assertEqual(result, {"title": "English title", "description": ""})
        self.assertEqual(len(self.requests), 1)

    def test_unchanged_name_is_allowed_when_description_is_translated(self):
        self.handler = lambda request: self.response(
            request, "Titolo italiano" if request.url.params["q"] == "Titolo italiano" else "English description",
        )
        result = self.translator.translate("Titolo italiano", "Descrizione italiana", "en", "it")
        self.assertEqual(result["description"], "English description")


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.youtube = Mock()
        self.youtube.update_localizations_only.return_value = True
        self.translator = Mock()
        self.translator.translate.return_value = {"title": "English title", "description": "English description"}
        self.store = Mock()
        self.cache = {"video": {
            "source_language_code": "it",
            "youtube_channel_id": "channel",
            "default_metadata": {"title": "Titolo italiano", "description": "Descrizione italiana"},
            "translated_languages": {"it": False, "en": False},
        }}

    def process(self, dry_run=False):
        with patch("main.LANGUAGE_MAP", {"it": "Italian", "en": "English"}):
            process_video(
                self.youtube, self.translator, "video", self.cache, self.store,
                Settings(dry_run=dry_run), force_fetch=False, force_retranslate=False,
            )

    def test_dry_run_does_not_mark_languages_as_completed(self):
        before = copy.deepcopy(self.cache)
        self.process(dry_run=True)
        self.assertEqual(self.cache, before)
        self.store.save.assert_not_called()
        self.youtube.update_localizations_only.assert_called_once_with(
            "video", {"en": self.translator.translate.return_value}, dry_run=True,
        )

    def test_failed_translation_is_never_uploaded_or_marked_completed(self):
        self.translator.translate.return_value = None
        self.process()
        self.youtube.update_localizations_only.assert_not_called()
        self.assertFalse(self.cache["video"]["translated_languages"]["en"])
        self.store.save.assert_not_called()

    def test_successful_upload_marks_completion_and_passes_source_language(self):
        self.process()
        self.translator.translate.assert_called_once_with(
            "Titolo italiano", "Descrizione italiana", "en", source_language_code="it",
        )
        self.assertTrue(self.cache["video"]["translated_languages"]["en"])
        self.store.save.assert_called_once_with(self.cache)

    def test_failed_upload_does_not_mark_completion(self):
        self.youtube.update_localizations_only.return_value = False
        with self.assertLogs(level="ERROR"):
            self.process()
        self.assertFalse(self.cache["video"]["translated_languages"]["en"])
        self.store.save.assert_not_called()


class CommandTests(unittest.TestCase):
    def test_service_check_does_not_access_youtube_or_cache(self):
        with (
            patch("main.parse_args", return_value=SimpleNamespace(dry_run=False, check_translation=True, all_languages=False)),
            patch("main.MetadataTranslator") as translator_class,
            patch("main.YouTubeClient") as youtube_class,
            patch("main.CacheStore") as cache_class,
            patch("main.load_video_ids") as load_ids,
        ):
            translator = translator_class.return_value
            translator.translate.return_value = {"title": "This is a translation test.", "description": ""}
            self.assertEqual(main(), 0)
            youtube_class.assert_not_called()
            cache_class.assert_not_called()
            load_ids.assert_not_called()
            translator.close.assert_called_once()

    def test_service_check_reports_block_without_traceback(self):
        with (
            patch("main.parse_args", return_value=SimpleNamespace(dry_run=False, check_translation=True, all_languages=False)),
            patch("main.MetadataTranslator") as translator_class,
        ):
            translator = translator_class.return_value
            translator.translate.side_effect = TranslationServiceBlocked("HTTP 429")
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main(), 1)
            translator.close.assert_called_once()

    def test_all_language_check_tests_title_and_description_and_reports_failure(self):
        with (
            patch("main.parse_args", return_value=SimpleNamespace(dry_run=False, check_translation=True, all_languages=True)),
            patch("main.LANGUAGE_MAP", {"it": "Italian", "en": "English", "fr": "French"}),
            patch("main.MetadataTranslator") as translator_class,
            patch("main.YouTubeClient") as youtube_class,
        ):
            translator = translator_class.return_value
            translator.translate.side_effect = [{"title": "Test", "description": "A description"}, None]
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main(), 1)
            calls = translator.translate.call_args_list
            self.assertEqual([call.args[2] for call in calls], ["en", "fr"])
            self.assertTrue(all(call.args[0] and call.args[1] for call in calls))
            youtube_class.assert_not_called()
            translator.close.assert_called_once()

    def test_block_stops_run_before_processing_other_videos(self):
        with (
            patch("main.parse_args", return_value=SimpleNamespace(
                dry_run=False, check_translation=False, force_fetch=False, force_retranslate=False,
            )),
            patch("main.MetadataTranslator") as translator_class,
            patch("main.YouTubeClient"),
            patch("main.CacheStore"),
            patch("main.load_video_ids", return_value=["first-video", "second-video"]),
            patch("main.process_video", side_effect=TranslationServiceBlocked("HTTP 429")) as process,
        ):
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main(), 1)
            process.assert_called_once()
            translator_class.return_value.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
