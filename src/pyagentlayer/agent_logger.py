# -*- coding:utf-8 -*-
import logging
import os
import queue

agent_logger_id = os.environ.get("LOGGER_AGENT_ID", "5")


class OnChainLog:
    agent_id: int
    task_id: str
    parent_task_id: str | None
    operation: str
    time_takes: int

    def __init__(self, agent_id: int, task_id: str, parent_task_id: str, operation: str, time_takes: int):
        self.agent_id = agent_id
        self.task_id = task_id
        self.parent_task_id = parent_task_id
        self.operation = operation
        self.time_takes = time_takes


log_queue: queue.Queue[OnChainLog] = queue.Queue()


def record_log(log: OnChainLog):
    global log_queue
    log_queue.put_nowait(log)


def record_log_sync(agent, log: OnChainLog):
    log.parent_task_id = "" if log.parent_task_id is None else log.parent_task_id
    agent.send(agent_logger_id, "log", log.__dict__)


def monitor_new_onchain_log(agent):
    global log_queue
    while True:
        log = log_queue.get()
        try:
            record_log_sync(agent, log)
        except Exception as e:
            logging.warning(f"record log on-chain failed with error message {e}")
            log_queue.put_nowait(log)
