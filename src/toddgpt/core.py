from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .prompt import SYSTEM_PROMPT
from .tools.grab_geom import extract_molecule_from_pubchem, read_geometry_from_file
from .tools.chemcloud_tool import RunTerachem
from .tools.mace_calc import MaceCalculator
from .tools.spectra import (
    GenerateSpectrum,
    OptimizeMolecule,
    RunHessian,
    RunTDDFT,
    CheckGeneratedSpectra,
)
from .tools.experimental_data import MaxWavelengthTool
from .tools.update_tc_input import UpdateTcInput
from .tools.search_lit import SearchLit
from .tools.frontend_tools import GrabImage

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
import json
import base64
import os


class Agent:
    def __init__(
        self,
        api_provider,
        api_key,
        api_url=None,
        api_model="gpt-4o",
        api_temperature=0,
    ):
        self.api_provider = api_provider
        self.api_key = api_key
        self.api_url = api_url
        self.api_model = api_model
        self.api_temperature = api_temperature

    def get_executor(self):
        if self.api_provider.lower() == "openai":
            supported_models = ["gpt-4o"]
            if self.api_model not in supported_models:
                raise ValueError(
                    f"Unsupported OpenAI model: {self.api_model}. Supported models are: {', '.join(supported_models)}"
                )

            llm = ChatOpenAI(
                model=self.api_model,
                temperature=self.api_temperature,
                openai_api_key=self.api_key,
                base_url=self.api_url,
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    ("human", "{conversation}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )
        else:
            raise ValueError("Unsupported API provider")

        tools = [
            extract_molecule_from_pubchem,
            RunTerachem(),
            MaceCalculator(),
            OptimizeMolecule(),
            RunHessian(),
            RunTDDFT(),
            GenerateSpectrum(),
            CheckGeneratedSpectra(),
            MaxWavelengthTool(),
            SearchLit(),
            UpdateTcInput(),
            GrabImage(),
        ]
        llm_with_tools = llm.bind_tools(tools)

        def process_agent_action(action):
            if isinstance(action, dict) and "image_data" in action:
                image_data = action["image_data"]
                if isinstance(image_data, str) and image_data.startswith(
                    "__FRONTEND_IMAGE__"
                ):
                    return "__IMAGE_PLACEHOLDER__"
                else:
                    return image_data
            return action

        agent = (
            {
                "conversation": lambda x: x["conversation"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    [
                        (action, process_agent_action(action))
                        for action, _ in x["intermediate_steps"]
                    ]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
