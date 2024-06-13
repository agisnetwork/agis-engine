import json
from urllib.parse import urljoin

from .models import AgentMetadata
from .registry_client import OnChainAgentRegistryClient
from .utils.base_request import BaseRequestClient


class AgentLink(BaseRequestClient):

    def __init__(self, agent_client: OnChainAgentRegistryClient) -> None:
        self.agent_client = agent_client
        self.agent_meta_cache = {}
        super().__init__()

    def _get_agent_meta(self, agent_id: int) -> AgentMetadata:
        if agent_id in self.agent_meta_cache:
            return self.agent_meta_cache[agent_id]
        else:
            agent_meta = self.agent_client.get_agent_meta(agent_id)
            self.agent_meta_cache[agent_id] = agent_meta
            return agent_meta

    def call(self, agent_id, task_id, method, parameters,
             current_agent_metadata: AgentMetadata,
             message_hash=None,
             signature=None,
             sync=True):
        headers = {
            "Content-Type": "application/json",
            "X-Agent-Meta": json.dumps(current_agent_metadata.to_json()),
            "X-Agent-Task-Id": task_id,
            "X-Agent-Message-Hash": message_hash,
            "X-Agent-Signature": signature
        }

        target_agent_meta = self._get_agent_meta(agent_id)
        url = urljoin(target_agent_meta.endpoint, method)
        if sync:
            return self.send(url, headers, parameters)
        else:
            return self.send_async(url, headers, parameters)
