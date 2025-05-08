"""
Tests for the Jobs ORM implementation.

This module tests the ORM functionality for persisting Jobs objects
to a database, including serialization, deserialization, and CRUD operations.
"""

import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from edsl.jobs.jobs import Jobs
from edsl.surveys import Survey
from edsl.questions import QuestionFreeText, QuestionMultipleChoice
from edsl.agents import Agent
from edsl.language_models import Model
from edsl.scenarios import Scenario

from edsl.jobs.orm import (
    Base,
    SQLJob,
    SQLJobParameter,
    save_job,
    load_job,
    update_job,
    delete_job,
    list_jobs,
    find_jobs_by_name,
    search_jobs
)


class TestJobsOrm(unittest.TestCase):
    """Test the Jobs ORM implementation."""

    def setUp(self):
        """Set up a new database for each test."""
        # Create a new in-memory SQLite database for each test
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        
        # Create a simple survey for testing
        q1 = QuestionFreeText(question_name="name", question_text="What is your name?")
        q2 = QuestionMultipleChoice(
            question_name="mood",
            question_text="How are you feeling?",
            question_options=["Happy", "Sad", "Neutral"]
        )
        self.survey = Survey(questions=[q1, q2])
        
    def prepare_job(self, job):
        """Helper to prepare a job for testing by clearing non-serializable attributes."""
        # Clear non-serializable attributes
        job.run_config.environment.bucket_collection = None
        job.run_config.environment.cache = None
        job.run_config.environment.jobs_runner_status = None
        return job

    def tearDown(self):
        """Clean up resources after each test."""
        self.session.close()
        Base.metadata.drop_all(self.engine)

    def test_save_and_load_job(self):
        """Test saving and loading a Jobs object."""
        # Create a test job
        job = Jobs(self.survey)
        
        # Add agents and scenarios only (models are not easily serializable)
        agent1 = Agent(traits={"status": "Happy"})
        agent2 = Agent(traits={"status": "Sad"})
        scenario1 = Scenario({"time": "morning"})
        scenario2 = Scenario({"time": "evening"})
        
        job.by(agent1, agent2).by(scenario1, scenario2)
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Manually clear models as they're not easily serializable
        job.models = []
        
        # Add name and description
        job_name = "Test Job"
        job_description = "A test job for ORM testing"
        
        # Save the job
        job_orm = save_job(self.session, job, name=job_name, description=job_description)
        self.session.commit()
        job_id = job_orm.id
        
        # Verify the job has an ORM ID
        self.assertTrue(hasattr(job, '_orm_id'))
        self.assertEqual(job._orm_id, job_id)
        
        # Verify basic attributes
        self.assertEqual(job_orm.name, job_name)
        self.assertEqual(job_orm.description, job_description)
        
        # Load the job
        loaded_job = load_job(self.session, job_id)
        
        # Verify job components were loaded correctly
        self.assertEqual(len(loaded_job.agents), 2)
        self.assertEqual(len(loaded_job.models), 0)  # No models since we cleared them
        self.assertEqual(len(loaded_job.scenarios), 2)
        
        # Verify agent traits
        self.assertEqual(loaded_job.agents[0].traits["status"], "Happy")
        self.assertEqual(loaded_job.agents[1].traits["status"], "Sad")
        
        # Verify scenario data
        self.assertEqual(loaded_job.scenarios[0]["time"], "morning")
        self.assertEqual(loaded_job.scenarios[1]["time"], "evening")

    def test_update_job(self):
        """Test updating an existing job."""
        # Create and save an initial job
        job = Jobs(self.survey)
        agent = Agent(traits={"status": "Happy"})
        job.by(agent)
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        job_orm = save_job(self.session, job, name="Initial Job")
        self.session.commit()
        job_id = job_orm.id
        
        # Update the job with new components
        updated_job = Jobs(self.survey)
        updated_agent = Agent(traits={"status": "Excited"})
        updated_scenario = Scenario({"time": "afternoon"})
        updated_job.by(updated_agent).by(updated_scenario)
        updated_job._orm_id = job._orm_id
        
        # Prepare updated job for testing
        updated_job = self.prepare_job(updated_job)
        
        # Update the job
        update_success = update_job(self.session, job_id, updated_job, name="Updated Job")
        self.session.commit()
        
        # Verify update was successful
        self.assertTrue(update_success)
        
        # Load the job again
        loaded_job = load_job(self.session, job_id)
        
        # Verify the updates
        self.assertEqual(loaded_job.agents[0].traits["status"], "Excited")
        self.assertEqual(loaded_job.scenarios[0]["time"], "afternoon")
        self.assertEqual(loaded_job.name, "Updated Job")

    def test_delete_job(self):
        """Test deleting a job."""
        # Create and save a job
        job = Jobs(self.survey)
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        job_orm = save_job(self.session, job)
        self.session.commit()
        job_id = job_orm.id
        
        # Delete the job
        success = delete_job(self.session, job_id)
        self.session.commit()
        
        # Verify deletion was successful
        self.assertTrue(success)
        self.assertIsNone(load_job(self.session, job_id))

    def test_list_jobs(self):
        """Test listing jobs with pagination."""
        # Create and save multiple jobs
        for i in range(5):
            job = Jobs(self.survey)
            job = self.prepare_job(job)
            save_job(self.session, job, name=f"Job {i}")
            
        self.session.commit()
        
        # List all jobs
        jobs = list_jobs(self.session)
        self.assertEqual(len(jobs), 5)
        
        # Test pagination
        jobs_page1 = list_jobs(self.session, limit=3, offset=0)
        jobs_page2 = list_jobs(self.session, limit=3, offset=3)
        self.assertEqual(len(jobs_page1), 3)
        self.assertEqual(len(jobs_page2), 2)

    def test_find_jobs_by_name(self):
        """Test finding jobs by name."""
        # Create and save jobs with different names
        job1 = Jobs(self.survey)
        job2 = Jobs(self.survey)
        job3 = Jobs(self.survey)
        
        job1 = self.prepare_job(job1)
        job2 = self.prepare_job(job2)
        job3 = self.prepare_job(job3)
        
        save_job(self.session, job1, name="Test Job")
        save_job(self.session, job2, name="Test Job")  # Duplicate name
        save_job(self.session, job3, name="Another Job")
        self.session.commit()
        
        # Find jobs by name
        test_jobs = find_jobs_by_name(self.session, "Test Job")
        another_jobs = find_jobs_by_name(self.session, "Another Job")
        
        self.assertEqual(len(test_jobs), 2)
        self.assertEqual(len(another_jobs), 1)
        
    def test_search_jobs(self):
        """Test searching for jobs by name or description."""
        # Create and save jobs with searchable content
        job1 = Jobs(self.survey)
        job2 = Jobs(self.survey)
        job3 = Jobs(self.survey)
        
        job1 = self.prepare_job(job1)
        job2 = self.prepare_job(job2)
        job3 = self.prepare_job(job3)
        
        save_job(self.session, job1, name="AI Experiment", description="Testing AI models")
        save_job(self.session, job2, name="User Research", description="Examining AI interactions")
        save_job(self.session, job3, name="Performance Test", description="Benchmark test")
        self.session.commit()
        
        # Search for jobs containing "AI"
        ai_jobs = search_jobs(self.session, "AI")
        self.assertEqual(len(ai_jobs), 2)
        
        # Search for jobs containing "Test"
        test_jobs = search_jobs(self.session, "Test")
        self.assertEqual(len(test_jobs), 2)  # "Testing AI models" and "Performance Test"

    def test_run_parameters(self):
        """Test persisting and loading run parameters."""
        # Create a job with custom run parameters
        job = Jobs(self.survey)
        job.run_config.parameters.n = 5
        job.run_config.parameters.progress_bar = True
        job.run_config.parameters.stop_on_exception = True
        job.run_config.parameters.verbose = False
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Save the job
        job_orm = save_job(self.session, job)
        self.session.commit()
        job_id = job_orm.id
        
        # Load the job
        loaded_job = load_job(self.session, job_id)
        
        # Verify run parameters were preserved
        self.assertEqual(loaded_job.run_config.parameters.n, 5)
        self.assertTrue(loaded_job.run_config.parameters.progress_bar)
        self.assertTrue(loaded_job.run_config.parameters.stop_on_exception)
        self.assertFalse(loaded_job.run_config.parameters.verbose)

    def test_where_clauses(self):
        """Test persisting and loading where clauses."""
        # Create a job with where clauses
        job = Jobs(self.survey)
        job.where("agent.status == 'Happy'")
        job.where("scenario.time == 'morning'")
        
        # Prepare job for testing
        job = self.prepare_job(job)
        
        # Save the job
        job_orm = save_job(self.session, job)
        self.session.commit()
        job_id = job_orm.id
        
        # Load the job
        loaded_job = load_job(self.session, job_id)
        
        # Verify where clauses were preserved
        self.assertEqual(len(loaded_job._where_clauses), 2)
        self.assertEqual(loaded_job._where_clauses[0], "agent.status == 'Happy'")
        self.assertEqual(loaded_job._where_clauses[1], "scenario.time == 'morning'")


if __name__ == '__main__':
    unittest.main()