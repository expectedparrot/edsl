#!/usr/bin/env python3
"""
Test cases for Qualtrics vibe functionality.
"""

import tempfile
import csv
from pathlib import Path
import unittest

from edsl.conjure.qualtrics import ImportQualtrics
from edsl.conjure.qualtrics.vibe import VibeConfig


class TestQualtricsVibeFunctionality(unittest.TestCase):
    """Test cases for vibe-powered question enhancement."""

    def create_test_csv(self, headers, question_texts, import_ids, responses):
        """Helper to create test CSV files."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        writer = csv.writer(temp_file)

        writer.writerow(headers)
        writer.writerow(question_texts)
        writer.writerow(import_ids)

        for response in responses:
            writer.writerow(response)

        temp_file.close()
        return temp_file.name

    def test_vibe_disabled_import(self):
        """Test import with vibe disabled (should work like normal import)."""

        headers = ["Q1", "Q2"]
        question_texts = ["What is your name?", "whats ur age???"]
        import_ids = ['{"ImportId":"QID1"}', '{"ImportId":"QID2"}']
        responses = [["John", "25"], ["Jane", "30"]]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            # Test with vibe explicitly disabled
            vibe_config = VibeConfig(enabled=False)
            importer = ImportQualtrics(csv_file, verbose=False, vibe_config=vibe_config)
            survey = importer.survey

            self.assertEqual(len(survey.questions), 2)
            # Questions should be unchanged
            self.assertEqual(survey.questions[1].question_text, "whats ur age???")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_vibe_config_creation(self):
        """Test VibeConfig creation and validation."""

        # Test default config
        config1 = VibeConfig()
        self.assertTrue(config1.enabled)
        self.assertEqual(config1.max_concurrent, 5)
        self.assertEqual(config1.timeout_seconds, 30)
        self.assertEqual(config1.temperature, 0.1)
        self.assertIsInstance(config1.system_prompt, str)
        self.assertGreater(len(config1.system_prompt), 100)  # Should have substantial prompt

        # Test custom config (updated for refactored API)
        config2 = VibeConfig(
            enabled=False,
            max_concurrent=10,
            timeout_seconds=60,
            temperature=0.5
        )
        self.assertFalse(config2.enabled)
        self.assertEqual(config2.max_concurrent, 10)
        self.assertEqual(config2.timeout_seconds, 60)
        self.assertEqual(config2.temperature, 0.5)
        # System prompt is now loaded from external file, not configurable in constructor
        self.assertIsInstance(config2.system_prompt, str)
        self.assertGreater(len(config2.system_prompt), 100)

    def test_import_without_vibe_config(self):
        """Test that import works normally without vibe_config parameter."""

        headers = ["Q1"]
        question_texts = ["Test question"]
        import_ids = ['{"ImportId":"QID1"}']
        responses = [["Answer1"], ["Answer2"]]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            # Import without vibe_config (should work normally)
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            self.assertEqual(len(survey.questions), 1)
            self.assertEqual(survey.questions[0].question_text, "Test question")

            # Should be able to run the survey
            results = importer.run()
            self.assertEqual(len(results), 2)

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_vibe_processor_initialization(self):
        """Test that vibe processor is initialized correctly."""

        headers = ["Q1"]
        question_texts = ["Test"]
        import_ids = ['{"ImportId":"QID1"}']
        responses = [["Answer"]]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            # Test with explicitly no vibe config
            importer1 = ImportQualtrics(csv_file, verbose=False, vibe_config=None)
            self.assertIsNone(importer1.vibe_processor)

            # Test with default vibe config (should create processor)
            importer_default = ImportQualtrics(csv_file, verbose=False)
            self.assertIsNotNone(importer_default.vibe_processor)
            self.assertTrue(importer_default.vibe_processor.config.enabled)

            # Test with vibe config disabled
            vibe_config_disabled = VibeConfig(enabled=False)
            importer2 = ImportQualtrics(csv_file, verbose=False, vibe_config=vibe_config_disabled)
            self.assertIsNotNone(importer2.vibe_processor)
            self.assertFalse(importer2.vibe_processor.config.enabled)

            # Test with vibe config enabled
            vibe_config_enabled = VibeConfig(enabled=True)
            importer3 = ImportQualtrics(csv_file, verbose=False, vibe_config=vibe_config_enabled)
            self.assertIsNotNone(importer3.vibe_processor)
            self.assertTrue(importer3.vibe_processor.config.enabled)

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_vibe_with_piping(self):
        """Test that vibe works correctly with piping functionality."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "whats ur name???",
            "Hello ${q://QID1/ChoiceValue}! how r u?"
        ]
        import_ids = ['{"ImportId":"QID1"}', '{"ImportId":"QID2"}']
        responses = [["John", "Hello John! how r u?"], ["Jane", "Hello Jane! how r u?"]]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            vibe_config = VibeConfig(
                enabled=True,
                max_concurrent=1,
                timeout_seconds=10
            )
            importer = ImportQualtrics(csv_file, verbose=False, vibe_config=vibe_config)
            survey = importer.survey

            self.assertEqual(len(survey.questions), 2)

            # Check that piping was converted to EDSL format
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            self.assertIsNotNone(q2)
            self.assertIn("{{ Q1.answer }}", q2.question_text)  # Piping should be preserved

            # Should still be able to run the survey
            results = importer.run()
            self.assertEqual(len(results), 2)

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_vibe_error_handling(self):
        """Test that vibe errors don't break the import process."""

        headers = ["Q1"]
        question_texts = ["Test question"]
        import_ids = ['{"ImportId":"QID1"}']
        responses = [["Answer"]]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            # Create config that might cause issues (very short timeout)
            vibe_config = VibeConfig(
                enabled=True,
                timeout_seconds=0.001,  # Very short timeout to trigger errors
                max_concurrent=1
            )

            # Should not raise exception even if vibe processing fails
            importer = ImportQualtrics(csv_file, verbose=False, vibe_config=vibe_config)
            survey = importer.survey

            # Survey should still be created
            self.assertEqual(len(survey.questions), 1)

            # Should still be able to run
            results = importer.run()
            self.assertEqual(len(results), 1)

        finally:
            Path(csv_file).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)