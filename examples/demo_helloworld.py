# -*- coding:utf-8 -*-
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from pyagentlayer import LAgent, Model, Context, run_agent

# 1. create agent
agent = LAgent(name="helloworld",
               description="say hello",
               http_endpoint=f"http://agent.mydomain.xyz/hello_world",
               private_key=os.environ['HELLO_WORLD_PRIVATE_KEY'],
               agent_id=os.environ['HELLO_WORLD_AGENT_ID'])


# 2. define agent's protocol , including request and response schema 
class Param(Model):
    msg: str

class Response(Model):
    code: int
    data: str

@agent.on_message("hello", Param, Response)
def echo_jerry(ctx: Context, param: Param):
    return Response(code=0, data=f"hello {param.msg}. {datetime.ctime(datetime.now())}")


# 3. run agent
if __name__ == "__main__":
    run_agent(agent)
