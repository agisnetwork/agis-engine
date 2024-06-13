# AgentLayerSDK

> AgentLayerSDK is a Python library designed to streamline Agent development.

- [AgentLayerSDK](#agentlayersdk)
    - [Install](#install)
    - [Usage](#usage)
        - [set up environment](#set-up-environment)
        - [Create an agent](#create-an-agent)
        - [Register](#register)
        - [Run Agent](#run-agent)
        - [Call other agent](#call-other-agent)
        - [Build a paid agent](#build-a-paid-agent)

## Install

Using Pip

`pip install PyAgentlayer`

## Usage

### set up environment

create `.env` file from .env.example, and edit `.env` file

```shell
HELLO_WORLD_PRIVATE_KEY=#Private Key#
HELLO_WORLD_AGENT_ID=#Agent ID#

IPFS_PARTICLE_PROJECT_ID=#Project ID#
IPFS_PARTICLE_SERVER_KEY=#Server Key#
```

`HELLO_WORLD_PRIVATE_KEY` is the private key of the agent, you can get it from [Metamask](https://metamask.io/).
`HELLO_WORLD_AGENT_ID` is the agent id, first you need to register agent with command `python demo_helloworld.py register`, then you will get an
agent_id, place it in `.env` file.

`IPFS_PARTICLE_PROJECT_ID' and `IPFS_PARTICLE_SERVER_KEY' is optional, they are used for store agent data, you can get it
from [Particle](https://dashboard.particle.network/).

### Create an agent

`demo_helloworld.py`

```python
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
def hello(ctx: Context, param: Param):
    return Response(code=0, data=f"hello {param.msg}. {datetime.ctime(datetime.now())}")


# 3. run agent
if __name__ == "__main__":
    run_agent(agent)
```

step 1, you need to create an agent with `LAgent` class, and provide agent's name, description, private_key, http_endpoint, agent_id.

> NOTE:
> 1. the infomation of agent, such as name, description, http_endpoint is unchangable once the agent is created.
> 2. the http_endpoint should be a public endpoint, which is used to interact with our agent.

step 2, define agent's protocol, including request and response schema, and define a function to handle the message.

step 3, run agent with `run_agent` function.

### Register

Before run agent, we should register agent with command: `python demo_helloworld.py register`

the output should be like this:

```shell
agent_id: 1
wallet_address:0xXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
smart_wallet_address:0xXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

now we get an agent_id, place the agent_id in `.env` file.

### Run Agent

`python demo_helloworld.py`

after agent running, we can get agent api info with `http://localhost:8000`.

### Call other agent

In the process of developing our Agent, we may need to utilize Agent services provided by others. In such cases, we can conveniently integrate and
test by using the API interfaces provided by AgentSDK.

How can we view the services provided by the Agent? We can directly access the endpoint of the third-party Agent in a web browser to obtain the
corresponding API documentation. The documentation will comprehensively list the paths provided, along with the request parameters and responses for
each path.

For example, if we call the `calc` method of agent 1, we can call it with the following code:

```python
target_agent_id = 1
res = agent.send(target_agent_id, "hello", {
    "msg": "hello, i am new agent"
})
```

or call by curl via openapi schema 
```shell
curl http://localhost:8000/hello --header 'Content-Type:application/json' --data-raw '{"msg": "hello, i am new agent"}' 


```


### Build a paid agent

We can create a **Paid Agent** that requires the caller to pay for its usage, thereby generating revenue. The paid agent can be easily developed and
registered using the AgentSDK, and it can also subscribe to and invoke other paid agents through the SDK. Below, we demonstrate how to create a paid
agent with a piece of code.

> NOTE: Currently, Paid Agents only support payment through ERC20 Token `Agent`.

```python
from pyagentlayer import LAgent, SubscriptionPlan, SubscriptionPeriodEnum

# define subscription plans, currently supporting three subscription types: weekly, monthly, yearly.
subscription_plans = [
    SubscriptionPlan(period=SubscriptionPeriodEnum.WEEKLY, price_in_agent=1),   # 1 Agent weekly
    SubscriptionPlan(period=SubscriptionPeriodEnum.MONTHLY, price_in_agent=4),  # 4 Agent monthly
    SubscriptionPlan(period=SubscriptionPeriodEnum.YEARLY, price_in_agent=40),  # 40 Agent yearly
]

agent = LAgent(name="plus",
               description="demo agent for plus",
               http_endpoint="http://agent.mydomain.xyz/plus",
               payable=True,  # payment represent this is a paid agent
               subscription_plan=subscription_plans,
               private_key=os.environ['PLUS_AGENT_PRIVATE_KEY'],
               agent_id=os.environ['PLUS_AGENT_AGENT_ID'])
```