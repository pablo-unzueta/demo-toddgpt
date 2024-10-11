import nest_asyncio

from paperqa import Settings, ask
from langchain_core.tools import BaseTool
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from pydantic import BaseModel
from typing import Type


nest_asyncio.apply()


class SearchLitInput(BaseModel):
    text: str


response_schemas = [
    ResponseSchema(name="answer", description="answer to the user's question"),
    ResponseSchema(
        name="answer",
        description="One word answer to the user's question",
    ),
]


class SearchLit(BaseTool):
    name: str = "search_literature"
    description: str = "Use this tool to update simulation parameters only if the default hasn't worked."
    args_schema: Type[BaseModel] = SearchLitInput

    def _run(self, text: str) -> str:
        paper_directory = "/Users/pablo/software/demo-toddgpt/assets/papers"
        answer = ask(
            text,
            settings=Settings(temperature=0.0, paper_directory=paper_directory),
        )
        return answer


if __name__ == "__main__":
    search_lit = SearchLit()
    print(
        search_lit._run(
            text="What basis set should I use for valence states?",
        )
    )
