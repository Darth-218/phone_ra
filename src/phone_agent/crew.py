from crewai import Crew, Process

from phone_agent.agents import extractor, fetcher, reporter, scout, validator
from phone_agent.tasks import (
    task_discover_urls,
    task_extract_specs,
    task_fetch_pages,
    task_report,
    task_validate,
)


crew = Crew(
    agents=[scout, fetcher, extractor, validator, reporter],
    tasks=[
        task_discover_urls,
        task_fetch_pages,
        task_extract_specs,
        task_validate,
        task_report,
    ],
    process=Process.sequential,
    verbose=True,
    memory=False,
)
