import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from prompt_factory.prompt_assembler import PromptAssembler
from prompt_factory.core_prompt import CorePrompt
from pyagentlayer import LAgent, Model, Context, run_agent
import tools.openai_api as openai_api
# 1. create agent
agent = LAgent(name="AgeisAgent",
               description="This is a code audit agent",
               http_endpoint=f"http://agent.mydomain.xyz/hello_world222",
               private_key=os.environ['HELLO_WORLD_PRIVATE_KEY'],
               agent_id=os.environ['HELLO_WORLD_AGENT_ID'])


# 2. define agent's protocol , including request and response schema 
class Param(Model):
    msg: str


class Response(Model):
    code: int
    data: str


@agent.on_message("hello", Param, Response)
def hello(ctx: Context, param: Param):
    code=param.msg
    prompt=PromptAssembler.assemble_prompt(code)
    res=[]
    for i in range(10):
        vul_res=openai_api.ask_openai_common(prompt)
        vul_check_prompt=PromptAssembler.assemble_vul_check_prompt(code,vul_res)
        vul_check_res=openai_api.ask_openai_common(vul_check_prompt)
        if '"result":"yes' in vul_check_res or '"result": "yes"' in vul_check_res:
            assumption_prompt=code+"\n\n"+vul_res+"\n\n"+CorePrompt.assumation_prompt()
            assumption_res=openai_api.ask_openai_common(assumption_prompt)
            if "dont need In-project other contract" in assumption_res:
                res.append(vul_res)


    return Response(code=0, data=res)


# 3. run agent
if __name__ == "__main__":
    run_agent(agent)