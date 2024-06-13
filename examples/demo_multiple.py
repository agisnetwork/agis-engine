# -*- coding:utf-8 -*-
import os
import json
from dotenv import load_dotenv

load_dotenv()

from pyagentlayer import LAgent, Model, Context, run_agent

agent = LAgent(name="multiple",
               http_endpoint="http://agent.mydomain.xyz/multiply",
               description="demo agent for multiple",
               private_key=os.environ['MULTIPLY_AGENT_PRIVATE_KEY'],
               agent_id=os.environ['MULTIPLY_AGENT_AGENT_ID'])


class Param(Model):
    value_a: int
    value_b: int


class Response(Model):
    value: int


@agent.on_message(request_type=Param, response_type=Response)
def multiple(ctx: Context, param: Param):
    plus_agent_id = os.environ['PLUS_AGENT_AGENT_ID']
    value = 0
    for i in range(param.value_b):
        # call other agent
        res = agent.send(plus_agent_id, "plus", {
            "value_a": value,
            "value_b": param.value_a
        })
        res = json.loads(res)
        value = res["value"]

    return Response(value=value)


if __name__ == '__main__':
    run_agent(agent, port=8001)
