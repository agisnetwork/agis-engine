# -*- coding:utf-8 -*-
import os

from dotenv import load_dotenv

load_dotenv()

from pyagentlayer import LAgent, Model, Context, run_agent, SubscriptionPlan, SubscriptionPeriodEnum

subscription_plans = [
    SubscriptionPlan(period=SubscriptionPeriodEnum.WEEKLY, price_in_agent=1),
    SubscriptionPlan(period=SubscriptionPeriodEnum.MONTHLY, price_in_agent=4),
    SubscriptionPlan(period=SubscriptionPeriodEnum.YEARLY, price_in_agent=40),
]

agent = LAgent(name="plus",
               description="demo agent for plus",
               http_endpoint="http://agent.mydomain.xyz/plus",
               payable=True,
               subscription_plan=subscription_plans,
               private_key=os.environ['PLUS_AGENT_PRIVATE_KEY'],
               agent_id=os.environ['PLUS_AGENT_AGENT_ID'])


class Param(Model):
    value_a: int
    value_b: int


class Response(Model):
    value: int


@agent.on_message(request_type=Param, response_type=Response)
def plus(ctx: Context, param: Param):
    return Response(value=param.value_a + param.value_b)


@agent.on_message(name="calc_sub", request_type=Param, response_type=Response)
def sub(ctx: Context, param: Param):
    return Response(value=param.value_a - param.value_b)


if __name__ == '__main__':
    run_agent(agent)
