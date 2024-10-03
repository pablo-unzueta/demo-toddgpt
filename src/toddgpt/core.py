from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

# from toddgpt.calculators.mace_calc import MaceCalculator
# from toddgpt.parsers.terachem import TerachemParser
# # from toddgpt.tools.interface import Interface
from .prompt import SYSTEM_PROMPT

# from toddgpt.tools.geom_reporter import GeomReporter
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
from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable
import json

# from langchain_community.tools import MoveFileTool
# from langchain_core.tools import MoveFileTool


def human_approval(msg: AIMessage) -> Runnable:
    tool_strs = "\n\n".join(
        json.dumps(tool_call, indent=2) for tool_call in msg.tool_calls
    )
    input_msg = (
        f"Do you approve of the following tool invocations?\n\n"
        f"{', '.join(tool_call['name'] for tool_call in msg.tool_calls)}\n\n"
        "Please respond with 'Y'/'Yes' to approve, or anything else to reject."
    )
    resp = input(input_msg)
    if resp.lower() not in ("yes", "y"):
        raise ValueError(f"Tool invocations not approved:\n\n{tool_strs}")
    return msg


class Agent:
    def __init__(
        self,
        api_provider,
        api_key,
        api_url=None,
        api_model="gpt-4o-2024-08-06",
        api_temperature=0,
    ):
        self.api_provider = api_provider
        self.api_key = api_key
        self.api_url = api_url
        self.api_model = api_model
        self.api_temperature = api_temperature

    def get_executor(self):
        if self.api_provider.lower() == "openai":
            supported_models = ["gpt-4o-2024-08-06", "gpt-4o-mini", "gpt-4o"]
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

        # tools = [Interface()]
        # tools = [
        #     get_distances,
        #     read_geometry_from_file,
        #     extract_molecule_from_pubchem,
        #     return_terachem_input,
        #     list_terachem_input_examples,
        #     get_terachem_input_example,
        #     setup_terachem_input,
        # ]
        tools = [
            # read_geometry_from_file,
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
        ]
        llm_with_tools = llm.bind_tools(tools)
        agent = (
            {
                "conversation": lambda x: x["conversation"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )
        # return AgentExecutor(agent=agent, tools=tools, verbose=True)
        # agent = (
        #     {
        #         "conversation": lambda x: x["conversation"],
        #         "agent_scratchpad": lambda x: format_to_openai_tool_messages(
        #             x["intermediate_steps"]
        #         ),
        #     }
        #     | prompt
        #     | llm_with_tools
        #     | human_approval
        #     | OpenAIToolsAgentOutputParser()
        # )
        return AgentExecutor(agent=agent, tools=tools, verbose=True)
