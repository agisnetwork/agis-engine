# -*- coding:utf-8 -*-
import argparse

from ..agent import LAgent
from ..models import SubscriptionPeriodEnum


def run_agent(agent: LAgent, host="0.0.0.0", port=8000, log_onchain=True):
    parser = argparse.ArgumentParser(description='Command line tool for agent development')
    subparsers = parser.add_subparsers(dest='subcommand', help='Subcommands')

    subparsers.add_parser('run', help='Run Agent')

    subparsers.add_parser('register', help='Register Agent')

    parser_subscribe = subparsers.add_parser('subscribe', help='Subscribe Agent')
    parser_subscribe.add_argument("agent_id", type=int, help="Agent Id to subscribe")
    parser_subscribe.add_argument("--plan", type=str, choices=["weekly", "monthly", "yearly"], default="monthly", help="Subscription plan")
    parser_subscribe.add_argument("--auto-renewal", type=bool, default=False, help="Auto renewal")

    args = parser.parse_args()

    if args.subcommand == 'register':
        agent.register()
    elif args.subcommand == 'subscribe':
        period = SubscriptionPeriodEnum.get_by_name(args.plan)
        agent.subscribe(args.agent_id, period, args.auto_renewal)
    elif args.subcommand == 'run' or args.subcommand is None:
        agent.initialize()
        agent.run(host=host, port=port, log_onchain=log_onchain)
    else:
        parser.error(f'Invalid subcommand: {args.subcommand}')
