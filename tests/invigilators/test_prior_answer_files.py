"""Tests for piping prior-answer files into a question's attachments.

Covers the index-aware ``prior_answer_files`` path in the PromptConstructor
(``{{ up.answer }}`` attaches all files, ``{{ up.answer[i] }}`` attaches one),
the placeholder that keeps raw file data out of the rendered text, the shape
detection used to recognize a raw QuestionFileUpload answer, and the
``download_url`` shortcut on ``FileStore.from_file_upload_answer``.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from edsl.agents import Agent
from edsl.invigilators.prompt_constructor import (
    PromptConstructor,
    _FileRefPlaceholder,
    _referenced_file_indices,
)
from edsl.language_models.model import Model
from edsl.questions import QuestionFileUpload, QuestionFreeText
from edsl.scenarios import FileStore, Scenario
from edsl.scenarios.file_store_list import FileStoreList
from edsl.surveys import Survey
from edsl.surveys.memory import MemoryPlan


class TestReferencedFileIndices(unittest.TestCase):
    """The pure regex helper that decides which files a text references."""

    def test_bare_reference_attaches_all(self):
        self.assertEqual(
            _referenced_file_indices("Describe {{ up.answer }}", "up"),
            (True, set()),
        )

    def test_single_index(self):
        self.assertEqual(
            _referenced_file_indices("Look at {{ up.answer[0] }}", "up"),
            (False, {0}),
        )

    def test_multiple_indices(self):
        attach_all, indices = _referenced_file_indices(
            "{{ up.answer[0] }} and {{ up.answer[2] }}", "up"
        )
        self.assertFalse(attach_all)
        self.assertEqual(indices, {0, 2})

    def test_whole_and_indexed_together_attaches_all(self):
        attach_all, indices = _referenced_file_indices(
            "{{ up.answer }} but especially {{ up.answer[1] }}", "up"
        )
        self.assertTrue(attach_all)
        self.assertEqual(indices, {1})

    def test_dynamic_subscript_defaults_to_all(self):
        # A non-integer subscript can't be resolved statically -> attach all.
        self.assertEqual(
            _referenced_file_indices("{{ up.answer[i] }}", "up"),
            (True, set()),
        )

    def test_whitespace_inside_subscript(self):
        self.assertEqual(
            _referenced_file_indices("{{ up.answer [ 3 ] }}", "up"),
            (False, {3}),
        )

    def test_word_boundary_does_not_bleed_across_names(self):
        # Name "up" must not pick up "upload"'s subscript.
        attach_all, indices = _referenced_file_indices("{{ upload.answer[3] }}", "up")
        self.assertEqual(indices, set())
        # And the longer name resolves its own index.
        self.assertEqual(
            _referenced_file_indices("{{ upload.answer[3] }}", "upload"),
            (False, {3}),
        )


class TestFileRefPlaceholder(unittest.TestCase):
    """The str subclass that renders <see file ...> for whole and indexed refs."""

    def test_str_is_whole_placeholder(self):
        self.assertEqual(str(_FileRefPlaceholder("up")), "<see file up>")

    def test_subscript_is_indexed_placeholder(self):
        self.assertEqual(_FileRefPlaceholder("up")[0], "<see file up[0]>")

    def test_json_serializes_as_string(self):
        import json

        self.assertEqual(json.dumps(_FileRefPlaceholder("up")), '"<see file up>"')

    def test_renders_through_sandboxed_jinja(self):
        # The real render path uses a SandboxedEnvironment; confirm it dispatches
        # __str__ and __getitem__ on the str subclass rather than blocking them.
        from jinja2.sandbox import SandboxedEnvironment

        env = SandboxedEnvironment()
        ph = _FileRefPlaceholder("up")
        self.assertEqual(env.from_string("{{ x }}").render(x=ph), "<see file up>")
        self.assertEqual(env.from_string("{{ x[0] }}").render(x=ph), "<see file up[0]>")


class TestPriorAnswerFileStores(unittest.TestCase):
    """The helper that turns a prior answer into a list of FileStores (or [])."""

    def setUp(self):
        self._paths = []
        self.fs = self._make_filestore(b"contents")

    def tearDown(self):
        for p in self._paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def _make_filestore(self, content, suffix=".txt"):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(content)
        f.close()
        self._paths.append(f.name)
        return FileStore(f.name)

    def test_single_filestore(self):
        self.assertEqual(
            PromptConstructor._prior_answer_file_stores(self.fs), [self.fs]
        )

    def test_file_store_list(self):
        fsl = FileStoreList(data=[self.fs])
        self.assertEqual(
            PromptConstructor._prior_answer_file_stores(fsl), list(fsl.data)
        )

    def test_plain_list_of_filestores(self):
        self.assertEqual(
            PromptConstructor._prior_answer_file_stores([self.fs]), [self.fs]
        )

    def test_non_file_values_return_empty(self):
        for value in ("just text", [], None, {"gcs_path": "x"}):
            self.assertEqual(PromptConstructor._prior_answer_file_stores(value), [])


class TestPriorAnswerFiles(unittest.TestCase):
    """End-to-end: a question that pipes a prior file-upload answer."""

    def setUp(self):
        self._paths = []
        self.fs1 = self._make_filestore(b"file one")
        self.fs2 = self._make_filestore(b"file two")

    def tearDown(self):
        for p in self._paths:
            try:
                os.remove(p)
            except OSError:
                pass

    def _make_filestore(self, content, suffix=".txt"):
        f = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        f.write(content)
        f.close()
        self._paths.append(f.name)
        return FileStore(f.name)

    def _make_constructor(self, question_text, current_answers):
        # Fresh objects each call: prior_answer_files mutates the survey's
        # canonical question objects, so tests must not share a survey.
        up = QuestionFileUpload(question_name="up", question_text="Upload a file.")
        q = QuestionFreeText(question_name="q1", question_text=question_text)
        survey = Survey([up, q])
        return PromptConstructor(
            agent=Agent(),
            question=q,
            scenario=Scenario(),
            survey=survey,
            model=Model(),
            current_answers=current_answers,
            memory_plan=MemoryPlan(survey=survey),
        )

    def test_whole_reference_attaches_all_files(self):
        fsl = FileStoreList(data=[self.fs1, self.fs2])
        c = self._make_constructor("Describe {{ up.answer }}", {"up": fsl})
        self.assertEqual(c.prior_answer_files, list(fsl.data))

    def test_indexed_reference_attaches_only_that_file(self):
        fsl = FileStoreList(data=[self.fs1, self.fs2])
        c = self._make_constructor("Look at {{ up.answer[0] }}", {"up": fsl})
        self.assertEqual(c.prior_answer_files, [list(fsl.data)[0]])

    def test_out_of_range_index_attaches_nothing(self):
        fsl = FileStoreList(data=[self.fs1, self.fs2])
        c = self._make_constructor("Look at {{ up.answer[5] }}", {"up": fsl})
        self.assertEqual(c.prior_answer_files, [])

    def test_text_answer_is_not_attached(self):
        c = self._make_constructor("You said {{ up.answer }}", {"up": "some text"})
        self.assertEqual(c.prior_answer_files, [])

    def test_no_reference_attaches_nothing(self):
        fsl = FileStoreList(data=[self.fs1])
        c = self._make_constructor("No piping here.", {"up": fsl})
        self.assertEqual(c.prior_answer_files, [])

    def test_placeholder_replaces_answer_text(self):
        fsl = FileStoreList(data=[self.fs1])
        c = self._make_constructor("Describe {{ up.answer }}", {"up": fsl})
        _ = c.prior_answer_files  # triggers the placeholder swap
        self.assertEqual(str(c.prior_answers_dict()["up"].answer), "<see file up>")

    def test_get_prompts_attaches_files_and_hides_metadata(self):
        fsl = FileStoreList(data=[self.fs1, self.fs2])
        c = self._make_constructor("Describe {{ up.answer }}", {"up": fsl})
        prompts = c.get_prompts()
        self.assertEqual(prompts.get("files_list", []), list(fsl.data))
        # The placeholder is in the text; the raw file value is not.
        self.assertIn("<see file up>", prompts["user_prompt"].text)


class TestIsFileUploadAnswer(unittest.TestCase):
    """The tightened shape check used to recognize a raw file-upload answer."""

    @staticmethod
    def _check(value):
        from edsl.runner.render import RenderService

        return RenderService._is_file_upload_answer(value)

    def test_valid_answer(self):
        self.assertTrue(self._check([{"type": "gcs", "gcs_path": "users/x/f"}]))

    def test_missing_type_rejected(self):
        self.assertFalse(self._check([{"gcs_path": "users/x/f"}]))

    def test_missing_gcs_path_rejected(self):
        self.assertFalse(self._check([{"type": "gcs"}]))

    def test_empty_gcs_path_rejected(self):
        self.assertFalse(self._check([{"type": "gcs", "gcs_path": ""}]))

    def test_non_list_rejected(self):
        self.assertFalse(self._check("users/x/f"))

    def test_empty_list_rejected(self):
        self.assertFalse(self._check([]))

    def test_mixed_list_rejected(self):
        self.assertFalse(
            self._check([{"type": "gcs", "gcs_path": "users/x/f"}, "not a dict"])
        )


class TestFromFileUploadAnswerDownloadUrl(unittest.TestCase):
    """The download_url shortcut that skips the Coop round-trip."""

    def test_download_url_skips_coop(self):
        file_info = {
            "type": "gcs",
            "gcs_path": "users/x/f",
            "name": "receipt.txt",
            "mime_type": "text/plain",
        }
        sentinel = object()
        with patch.object(
            FileStore, "from_url", return_value=sentinel
        ) as mock_from_url, patch("edsl.coop.Coop") as mock_coop:
            result = FileStore.from_file_upload_answer(
                file_info, download_url="http://signed.example/f"
            )

        self.assertIs(result, sentinel)
        mock_coop.assert_not_called()
        # The provided URL is what gets fetched.
        self.assertEqual(mock_from_url.call_args.args[0], "http://signed.example/f")


class TestRestoreUploadAnswersError(unittest.TestCase):
    """A download failure names the question, not the gcs_path, and stays loud."""

    def test_failure_names_key_not_path(self):
        from edsl.runner.render import RenderService
        from edsl.runner.storage import InMemoryStorage

        service = RenderService(InMemoryStorage())
        current_answers = {
            "receipt": [{"type": "gcs", "gcs_path": "users/secret/path"}]
        }
        with patch.object(
            FileStore, "from_file_upload_answer", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError) as ctx:
                service._restore_upload_answers(current_answers)

        message = str(ctx.exception)
        self.assertIn("receipt", message)
        self.assertNotIn("users/secret/path", message)


if __name__ == "__main__":
    unittest.main()
