from langchain.agents import AgentExecutor
from langchain.agents.format_scratchpad.openai_tools import (
    format_to_openai_tool_messages,
)
from langchain.agents.output_parsers.openai_tools import OpenAIToolsAgentOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory

from .prompt import SYSTEM_PROMPT
from .tools.grab_geom import ExtractMoleculeFromPubchem
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
import openai
import json
import base64
import os
import time
import random


def call_openai_with_retry(func, *args, **kwargs):
    max_retries = 5
    base_delay = 1

    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except openai.RateLimitError as e:
            if attempt == max_retries - 1:
                raise

            delay = (2**attempt) + random.random()
            print(f"Rate limit hit. Retrying in {delay:.2f} seconds...")
            time.sleep(delay)


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
        self.memory = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )

    def get_executor(self):
        if self.api_provider.lower() == "openai":
            supported_models = ["gpt-4o-2024-08-06", "gpt-4o-mini"]
            if self.api_model not in supported_models:
                raise ValueError(
                    f"Unsupported OpenAI model: {self.api_model}. Supported models are: {', '.join(supported_models)}"
                )

            llm = ChatOpenAI(
                model=self.api_model,
                temperature=self.api_temperature,
                openai_api_key=self.api_key,
                base_url=self.api_url,
                streaming=True,
            )
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", SYSTEM_PROMPT),
                    MessagesPlaceholder(variable_name="chat_history"),
                    ("human", "{conversation}"),
                    MessagesPlaceholder(variable_name="agent_scratchpad"),
                ]
            )
        else:
            raise ValueError("Unsupported API provider")

        tools = [
            ExtractMoleculeFromPubchem(),
            RunTerachem(),
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
        agent = (
            {
                "conversation": lambda x: x["conversation"],
                "chat_history": lambda x: x["chat_history"],
                "agent_scratchpad": lambda x: format_to_openai_tool_messages(
                    x["intermediate_steps"]
                ),
            }
            | prompt
            | llm_with_tools
            | OpenAIToolsAgentOutputParser()
        )

        # Remove base64 strings from memory
        def clean_memory(messages):
            import re

            base64_pattern = re.compile(r"data:image/\w+;base64,[a-zA-Z0-9+/=]+")
            return [
                {
                    k: base64_pattern.sub("[BASE64_IMAGE]", v)
                    if isinstance(v, str)
                    else v
                    for k, v in msg.items()
                }
                for msg in messages
            ]

        self.memory.chat_memory.messages = clean_memory(
            self.memory.chat_memory.messages
        )
        return AgentExecutor(agent=agent, tools=tools, verbose=True, memory=self.memory)


# class Agent:
#     def __init__(
#         self,
#         api_provider,
#         api_key,
#         api_url=None,
#         api_model="gpt-4o-2024-08-06",
#         api_temperature=0,
#     ):
#         self.api_provider = api_provider
#         self.api_key = api_key
#         self.api_url = api_url
#         self.api_model = api_model
#         self.api_temperature = api_temperature
#         self.molecule_extracted = False

#     def get_executor(self):
#         if self.api_provider.lower() == "openai":
#             supported_models = ["gpt-4o-mini", "gpt-4o-2024-08-06"]
#             if self.api_model not in supported_models:
#                 raise ValueError(
#                     f"Unsupported OpenAI model: {self.api_model}. Supported models are: {', '.join(supported_models)}"
#                 )

#             llm = ChatOpenAI(
#                 model=self.api_model,
#                 temperature=self.api_temperature,
#                 openai_api_key=self.api_key,
#                 base_url=self.api_url,
#             )
#             prompt = ChatPromptTemplate.from_messages(
#                 [
#                     ("system", SYSTEM_PROMPT),
#                     ("human", "{conversation}"),
#                     MessagesPlaceholder(variable_name="agent_scratchpad"),
#                 ]
#             )
#         else:
#             raise ValueError("Unsupported API provider")

#         tools = [
#             ExtractMoleculeFromPubchem(),
#             RunTerachem(),
#             # MaceCalculator(),
#             OptimizeMolecule(),
#             RunHessian(),
#             RunTDDFT(),
#             GenerateSpectrum(),
#             CheckGeneratedSpectra(),
#             MaxWavelengthTool(),
#             SearchLit(),
#             UpdateTcInput(),
#             GrabImage(),
#         ]
#         llm_with_tools = llm.bind_tools(tools)

#         def process_agent_action(action):
#             if isinstance(action, dict):
#                 if "image_data" in action:
#                     image_data = action["image_data"]
#                     if isinstance(image_data, str) and image_data.startswith(
#                         "__FRONTEND_IMAGE__"
#                     ):
#                         return "__IMAGE_PLACEHOLDER__"
#                     else:
#                         return image_data

#         agent = (
#             {
#                 "conversation": lambda x: x["conversation"],
#                 "agent_scratchpad": lambda x: format_to_openai_tool_messages(
#                     [
#                         (action, process_agent_action(action))
#                         for action, _ in x["intermediate_steps"]
#                     ]
#                 ),
#             }
#             | prompt
#             | llm_with_tools
#             | OpenAIToolsAgentOutputParser()
#         )
#         return AgentExecutor(agent=agent, tools=tools, verbose=True)

#     def run(self, input_text):
#         executor = self.get_executor()
#         return executor.run(input_text)
