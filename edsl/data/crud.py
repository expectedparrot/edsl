from sqlalchemy import desc
from typing import Union
from edsl.data import Database, database, LLMOutputDataDB
from edsl.data.orm import ResultDB


class CRUDOperations:
    """
    A class that implementes CRUD operations for the EDSL package.

    Initalization:
    - `database`: A Database object.

    Methods:
    - `get_LLMOutputData(model, parameters, system_prompt, prompt)`: Retrieves a cached LLM output from the database.
    - `write_LLMOutputData(model, parameters, system_prompt, prompt, output)`: Writes an LLM output to the database.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def get_LLMOutputData(
        self, model: str, parameters: str, system_prompt: str, prompt: str
    ) -> Union[str, None]:
        """
        Retrieves a cached LLM output from the database. Arguments: in string format, the model, parameters, system_prompt, and prompt used to generate the output. Returns the output (json string) if it exists, otherwise None.
        """
        with self.database.get_db() as db:
            record = (
                db.query(LLMOutputDataDB)
                .filter_by(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=model,
                    parameters=parameters,
                )
                .order_by(desc(LLMOutputDataDB.id))
                .first()
            )
        return record.output if record else None

    def write_LLMOutputData(
        self, model: str, parameters: str, system_prompt: str, prompt: str, output: str
    ) -> None:
        """
        Writes an LLM output to the database. Arguments: in string format, the model, parameters, system_prompt, prompt, and the generated output.
        """
        record = LLMOutputDataDB(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            prompt=prompt,
            output=output,
        )

        with self.database.get_db() as db:
            db.add(record)
            db.commit()

    def write_result(
        self,
        job_uuid: str,
        result_uuid: str,
        agent: str,
        scenario: str,
        model: str,
        answer: str,
    ) -> None:
        """Writes a Result record to the database."""
        record = ResultDB(
            job_uuid=job_uuid,
            result_uuid=result_uuid,
            agent=agent,
            scenario=scenario,
            model=model,
            answer=answer,
        )

        with self.database.get_db() as db:
            db.add(record)
            db.commit()

    def read_results(self, job_uuid: str) -> list[ResultDB]:
        """Reads all Result records associated with job_uuid from the database."""
        with self.database.get_db() as db:
            records = (
                db.query(ResultDB)
                .filter_by(job_uuid=job_uuid)
                .order_by(desc(ResultDB.id))
                .all()
            )
        return records


CRUD = CRUDOperations(database)
