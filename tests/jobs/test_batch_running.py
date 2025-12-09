"""Unit tests for the Jobs.run_batch method."""

from edsl.jobs import Jobs
from edsl import Model, Question, Agent, Survey


class TestJobsBatchRunning:
    """Test cases for the run_batch method."""

    def test_run_batch_basic_functionality(self):
        """Test basic batch running functionality."""
        # Create a simple job
        job = Jobs.example().by(Model('test'))

        # Run with 2 batches
        results = job.run_batch(
            num_batches=2,
            disable_remote_inference=True,
            progress_bar=False
        )

        # Verify we get results
        assert results is not None
        assert len(results) > 0

    def test_run_batch_single_batch(self):
        """Test batch running with a single batch (should work like regular run)."""
        job = Jobs.example().by(Model('test'))

        results = job.run_batch(
            num_batches=1,
            disable_remote_inference=True,
            progress_bar=False
        )

        # Should still return valid results
        assert results is not None
        assert len(results) > 0

    def test_run_batch_more_batches_than_interviews(self):
        """Test batch running when num_batches > number of interviews."""
        # Create a job with minimal interviews
        q = Question("free_text", question_name="test", question_text="What is 1+1?")
        survey = Survey([q])
        job = Jobs(survey).by(Agent.example()).by(Model('test'))

        results = job.run_batch(
            num_batches=5,  # More batches than interviews
            disable_remote_inference=True,
            progress_bar=False
        )

        assert results is not None
        assert len(results) >= 1  # Should have at least one result

    def test_run_batch_preserves_results_structure(self):
        """Test that batch running preserves the expected Results structure."""
        job = Jobs.example().by(Model('test'))

        results = job.run_batch(
            num_batches=2,
            disable_remote_inference=True,
            progress_bar=False
        )

        # Check that results has expected attributes
        assert hasattr(results, 'data')
        assert hasattr(results, 'survey')

        # Check that we can access basic Results methods
        assert hasattr(results, 'select')
        assert hasattr(results, 'filter')

    def test_run_batch_with_different_batch_sizes(self):
        """Test batch running with various batch sizes."""
        job = Jobs.example().by(Model('test'))

        # Test different batch counts
        for num_batches in [1, 2, 3]:
            results = job.run_batch(
                num_batches=num_batches,
                disable_remote_inference=True,
                progress_bar=False
            )
            assert results is not None
            assert len(results) > 0

    def test_run_batch_attributes_handling(self):
        """Test that batch results properly handle optional attributes like bucket_collection."""
        job = Jobs.example().by(Model('test'))

        results = job.run_batch(
            num_batches=2,
            disable_remote_inference=True,
            progress_bar=False
        )

        # Should not raise an AttributeError even if bucket_collection doesn't exist
        assert results is not None

        # Should have cache attribute
        assert hasattr(results, 'cache')