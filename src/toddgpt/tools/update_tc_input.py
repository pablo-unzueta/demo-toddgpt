from pydantic import BaseModel
from langchain_core.tools import BaseTool
from typing import Type


class TemplateTcInput(BaseModel):
    tc_input: str
    keyword_to_change: str
    new_value: str


class UpdateTcInput(BaseTool):
    name: str = "update_tc_input"
    description: str = "Use this tool to update the tc_input file with the keyword value before running TDDFT. You will get back another tc_input string."
    args_schema: Type[BaseModel] = TemplateTcInput

    def _run(self, tc_input: str, keyword_to_change: str, new_value: str) -> str:
        lines = tc_input.split("\n")
        updated_lines = []
        for line in lines:
            if line.startswith(keyword_to_change):
                parts = line.split(None, 1)
                if len(parts) > 1:
                    updated_line = f"{parts[0]} {new_value}"
                else:
                    updated_line = f"{parts[0]} {new_value}"
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)
        updated_tc_input = "\n".join(updated_lines)
        return updated_tc_input

if __name__ == "__main__":
    update_tc_input = UpdateTcInput()
    updated_tc_input = update_tc_input._run(
        tc_input="""basis def2-svp
method wpbe
rc_w 0.3
charge 0
spinmult 1
maxit 100
coordinates geom.xyz
purify no
cis yes""",
        keyword_to_change="basis",
        new_value="aug-cc-pvdz",
    )

    print(updated_tc_input)

