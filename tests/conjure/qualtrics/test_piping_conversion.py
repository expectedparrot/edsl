#!/usr/bin/env python3
"""
Test cases for Qualtrics piping conversion to EDSL format.

This module tests the conversion of Qualtrics piping syntax (${q://QID/FieldType})
to EDSL piping syntax ({{ question_name.answer }}) in the ImportQualtrics class.
"""

import tempfile
import csv
from pathlib import Path
import unittest

# Import ImportQualtrics from the proper location
from edsl.conjure.qualtrics import ImportQualtrics


class TestQualtricsPipingConversion(unittest.TestCase):
    """Test cases for Qualtrics piping conversion to EDSL format."""

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

    def test_basic_choice_value_piping(self):
        """Test basic ${q://QID/ChoiceValue} to {{ question_name.answer }} conversion."""

        headers = ["Q1", "Q2", "Q3"]
        question_texts = [
            "What is your favorite color?",
            "You chose ${q://QID1/ChoiceValue}. Why do you like ${q://QID1/ChoiceValue}?",
            "Rate your satisfaction with ${q://QID1/ChoiceValue}."
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}',
            '{"ImportId":"QID3"}'
        ]
        responses = [
            ["Blue", "Blue is calming", "5"],
            ["Red", "Red is energetic", "4"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            # Find Q2 and Q3 which should have converted piping
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            q3 = next((q for q in survey.questions if q.question_name == "Q3"), None)

            self.assertIsNotNone(q2, "Q2 should exist in survey")
            self.assertIsNotNone(q3, "Q3 should exist in survey")

            # Verify conversion to EDSL syntax
            expected_q2 = "You chose {{ Q1.answer }}. Why do you like {{ Q1.answer }}?"
            expected_q3 = "Rate your satisfaction with {{ Q1.answer }}."

            self.assertEqual(q2.question_text, expected_q2,
                           f"Q2 piping not converted correctly. Got: {q2.question_text}")
            self.assertEqual(q3.question_text, expected_q3,
                           f"Q3 piping not converted correctly. Got: {q3.question_text}")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_multiple_question_piping(self):
        """Test piping from multiple different questions."""

        headers = ["Q1", "Q2", "Q3"]
        question_texts = [
            "What is your name?",
            "What is your age?",
            "Hello ${q://QID1/ChoiceValue}, you are ${q://QID2/ChoiceValue} years old."
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}',
            '{"ImportId":"QID3"}'
        ]
        responses = [
            ["Alice", "25", "Hello Alice, you are 25 years old."],
            ["Bob", "30", "Hello Bob, you are 30 years old."],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            q3 = next((q for q in survey.questions if q.question_name == "Q3"), None)
            self.assertIsNotNone(q3, "Q3 should exist in survey")

            expected_q3 = "Hello {{ Q1.answer }}, you are {{ Q2.answer }} years old."
            self.assertEqual(q3.question_text, expected_q3,
                           f"Multi-question piping not converted correctly. Got: {q3.question_text}")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_question_text_piping(self):
        """Test ${q://QID/QuestionText} piping resolution to static text."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "Rate our customer service",
            "You were asked: '${q://QID1/QuestionText}'. Please elaborate."
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}'
        ]
        responses = [
            ["5", "The service was excellent"],
            ["3", "It was okay"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            self.assertIsNotNone(q2, "Q2 should exist in survey")

            # QuestionText piping should be resolved to the actual question text
            expected_q2 = "You were asked: 'Rate our customer service'. Please elaborate."
            self.assertEqual(q2.question_text, expected_q2,
                           f"QuestionText piping not resolved correctly. Got: {q2.question_text}")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_complex_qid_formats(self):
        """Test handling of complex QID formats like QID148#1_1."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "Select your preference",
            "You selected ${q://QID148/ChoiceValue}."
        ]
        import_ids = [
            '{"ImportId":"QID148#1_1"}',  # Complex format
            '{"ImportId":"QID149#2_1"}'
        ]
        responses = [
            ["Option A", "You selected Option A."],
            ["Option B", "You selected Option B."],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)

            # Verify QID mapping was created correctly
            self.assertIn("QID148", importer.piping_resolver.qid_to_question_name,
                         "QID148 should be mapped despite complex format")
            self.assertEqual(importer.piping_resolver.qid_to_question_name["QID148"], "Q1",
                           "QID148 should map to Q1")

            survey = importer.survey
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            self.assertIsNotNone(q2, "Q2 should exist in survey")

            expected_q2 = "You selected {{ Q1.answer }}."
            self.assertEqual(q2.question_text, expected_q2,
                           f"Complex QID piping not converted correctly. Got: {q2.question_text}")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_no_piping_preserved(self):
        """Test that questions without piping are unchanged."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "What is your name?",
            "What is your favorite color?"
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}'
        ]
        responses = [
            ["Alice", "Blue"],
            ["Bob", "Red"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            q1 = next((q for q in survey.questions if q.question_name == "Q1"), None)
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)

            self.assertIsNotNone(q1, "Q1 should exist in survey")
            self.assertIsNotNone(q2, "Q2 should exist in survey")

            # Questions without piping should be unchanged
            self.assertEqual(q1.question_text, "What is your name?")
            self.assertEqual(q2.question_text, "What is your favorite color?")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_tab_file_format(self):
        """Test that tab-separated files work correctly with piping."""

        # Create a tab-separated file
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.tab', delete=False)

        # Write tab-separated data
        temp_file.write("Q1\tQ2\n")
        temp_file.write("What is your name?\tHello ${q://QID1/ChoiceValue}!\n")
        temp_file.write('{"ImportId":"QID1"}\t{"ImportId":"QID2"}\n')
        temp_file.write("Alice\tHello Alice!\n")
        temp_file.write("Bob\tHello Bob!\n")
        temp_file.close()

        try:
            importer = ImportQualtrics(temp_file.name, verbose=False)
            survey = importer.survey

            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            self.assertIsNotNone(q2, "Q2 should exist in survey")

            expected_q2 = "Hello {{ Q1.answer }}!"
            self.assertEqual(q2.question_text, expected_q2,
                           f"Tab file piping not converted correctly. Got: {q2.question_text}")

        finally:
            Path(temp_file.name).unlink(missing_ok=True)

    def test_piping_detection_and_mapping(self):
        """Test that piping detection provides correct statistics and mappings."""

        headers = ["Q1", "Q2", "Q3", "Q4"]
        question_texts = [
            "What is your name?",
            "Hello ${q://QID1/ChoiceValue}!",
            "Your name ${q://QID1/ChoiceValue} has ${q://QID1/ChoiceValue} characters.",
            "No piping here"
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}',
            '{"ImportId":"QID3"}',
            '{"ImportId":"QID4"}'
        ]
        responses = [
            ["Alice", "Hello Alice!", "Your name Alice has 5 characters.", "Plain text"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)

            # Should detect the piping pattern
            self.assertEqual(len(importer.piping_resolver.piping_patterns), 1,
                           f"Should detect 1 unique piping pattern, got {len(importer.piping_resolver.piping_patterns)}")

            pattern, qid, field_type, fmt = importer.piping_resolver.piping_patterns[0]
            self.assertEqual(pattern, "${q://QID1/ChoiceValue}", "Should detect correct pattern")
            self.assertEqual(qid, "QID1", "Should extract correct QID")
            self.assertEqual(field_type, "ChoiceValue", "Should extract correct field type")
            self.assertEqual(fmt, "format1", "Should identify as format1")

            # Should have QID mappings for all questions
            self.assertIn("QID1", importer.piping_resolver.qid_to_question_name, "Should map QID1")
            self.assertEqual(importer.piping_resolver.qid_to_question_name["QID1"], "Q1", "Should map QID1 to Q1")

            # Verify survey has converted piping
            survey = importer.survey
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            q3 = next((q for q in survey.questions if q.question_name == "Q3"), None)

            self.assertIsNotNone(q2)
            self.assertIsNotNone(q3)

            self.assertEqual(q2.question_text, "Hello {{ Q1.answer }}!")
            self.assertEqual(q3.question_text, "Your name {{ Q1.answer }} has {{ Q1.answer }} characters.")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_bracket_piping_format(self):
        """Test bracket-style piping format: [QID-FieldType-SubField]."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "What type of work do you do?",
            "Looking ahead to the next 3 months, how do you expect the volume of work in [QID4-ChoiceGroup-SelectedChoices] to change? Select one."
        ]
        import_ids = [
            '{"ImportId":"QID4"}',
            '{"ImportId":"QID5"}'
        ]
        responses = [
            ["Software Development", "Significantly more work"],
            ["Data Analysis", "The same amount of work"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)

            # Should detect the bracket piping pattern
            self.assertEqual(len(importer.piping_resolver.piping_patterns), 1,
                           f"Should detect 1 bracket piping pattern, got {len(importer.piping_resolver.piping_patterns)}")

            pattern, qid, field_type, fmt = importer.piping_resolver.piping_patterns[0]
            self.assertEqual(pattern, "[QID4-ChoiceGroup-SelectedChoices]", "Should detect correct bracket pattern")
            self.assertEqual(qid, "QID4", "Should extract correct QID")
            self.assertEqual(field_type, "ChoiceValue", "Should map ChoiceGroup-SelectedChoices to ChoiceValue")
            self.assertEqual(fmt, "format2", "Should identify as format2")

            # Verify conversion in survey
            survey = importer.survey
            q2 = next((q for q in survey.questions if q.question_name == "Q2"), None)
            self.assertIsNotNone(q2, "Q2 should exist in survey")

            expected_text = "Looking ahead to the next 3 months, how do you expect the volume of work in {{ Q1.answer }} to change? Select one."
            self.assertEqual(q2.question_text, expected_text,
                           f"Bracket piping not converted correctly. Got: {q2.question_text}")

        finally:
            Path(csv_file).unlink(missing_ok=True)

    def test_edsl_survey_creation(self):
        """Test that surveys with converted piping can be created and used in EDSL."""

        headers = ["Q1", "Q2"]
        question_texts = [
            "What is your favorite color?",
            "You chose ${q://QID1/ChoiceValue}. How does ${q://QID1/ChoiceValue} make you feel?"
        ]
        import_ids = [
            '{"ImportId":"QID1"}',
            '{"ImportId":"QID2"}'
        ]
        responses = [
            ["Blue", "Blue makes me feel calm"],
            ["Red", "Red makes me feel energetic"],
        ]

        csv_file = self.create_test_csv(headers, question_texts, import_ids, responses)

        try:
            importer = ImportQualtrics(csv_file, verbose=False)
            survey = importer.survey

            # Verify survey can be created
            self.assertIsNotNone(survey)
            self.assertEqual(len(survey.questions), 2)

            # Verify piping conversion
            q2 = survey.questions[1]
            expected_text = "You chose {{ Q1.answer }}. How does {{ Q1.answer }} make you feel?"
            self.assertEqual(q2.question_text, expected_text)

            # Verify survey can be serialized (important for EDSL compatibility)
            try:
                survey_dict = survey.to_dict()
                self.assertIsInstance(survey_dict, dict)
                self.assertIn('questions', survey_dict)
            except Exception as e:
                self.fail(f"Survey with piping should be serializable: {e}")

        finally:
            Path(csv_file).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)