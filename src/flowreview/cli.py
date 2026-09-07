"""Command-line interface for FlowReview evaluations."""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
from . import __version__, data, protocol, runners
from .providers import Provider, Route

SUITES = ('permission', 'assembly', 'policy-update', 'agentdojo')


def nonnegative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError('Must be nonnegative')
    return number


def route_config(args):
    base_env = 'ANTHROPIC_BASE_URL' if args.provider == 'anthropic' else 'OPENAI_BASE_URL'
    route = Route(provider=args.provider, model=args.model or os.getenv('FLOWREVIEW_MODEL', ''),
                  base_url=args.base_url or os.getenv(base_env, ''), api_key_env=args.api_key_env or '',
                  region=args.region, token_parameter=args.token_parameter, temperature=args.temperature)
    routes = {}
    if args.routing:
        for alias, values in protocol.read(args.routing).items():
            settings = {**asdict(route), **values}
            if values.get('provider', route.provider) != route.provider:
                for field in ('api_key_env', 'base_url'):
                    if field not in values:
                        settings[field] = ''
            routes[alias] = Route(**settings)
    if route.provider != 'mock' and not route.model and not routes:
        raise ValueError('Supply --model or set FLOWREVIEW_MODEL')
    if args.suite == 'agentdojo' and (route.provider == 'mock' or any(r.provider == 'mock' for r in routes.values())):
        raise ValueError('AgentDojo requires a model with tool calling')
    return route, routes


def inspect_results(path):
    report = protocol.read(Path(path) / 'summary.json')
    print(f"Status: {report['status']}")
    print(f"Model requests: {report['provider_attempts']}   Failed: {report['failed_calls']}")
    for arm, metrics in report['metrics'].items():
        fields = [f'{key}={value:.4f}' if isinstance(value, float) else f'{key}={value}' for key, value in metrics.items()]
        print(arm + ': ' + ', '.join(fields))


def main(argv=None):
    parser = argparse.ArgumentParser(description='FlowReview: deny without disabling multi-agent capabilities')
    parser.add_argument('--version', action='version', version=__version__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect', help='Read a completed evaluation')
    inspect.add_argument('path', type=Path)
    run = sub.add_parser('run', help='Run an evaluation')
    run.add_argument('--suite', choices=SUITES, default='assembly')
    run.add_argument('--provider', choices=('openai', 'anthropic', 'bedrock', 'mock'), default='openai')
    run.add_argument('--model')
    run.add_argument('--base-url')
    run.add_argument('--api-key-env')
    run.add_argument('--region', default=os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1')))
    run.add_argument('--token-parameter', choices=('max_tokens', 'max_completion_tokens'), default='max_completion_tokens')
    run.add_argument('--temperature', type=float, default=None)
    run.add_argument('--routing', help='JSON mapping of agent model names to connection settings')
    run.add_argument('--limit', type=nonnegative, default=1, help='Number of comparison units, 0 selects all')
    run.add_argument('--split', choices=('development', 'confirmation'), default='confirmation')
    run.add_argument('--output', type=Path)
    run.add_argument('--data-root')
    run.add_argument('--timeout', type=float, default=120)
    run.add_argument('--retries', type=nonnegative, default=2)
    run.add_argument('--dry-run', action='store_true', help='Show the evaluation selection without model requests')
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            inspect_results(args.path)
            return 0
        repo = data.root(args.data_root)
        os.environ['FLOWREVIEW_DATA_ROOT'] = str(repo)
        route, routes = route_config(args)
        plan, aliases = selection(repo, args)
        selected_routes = [routes.get(alias, route) for alias in aliases]
        fixture_only = all(r.provider == 'mock' for r in selected_routes)
        if any(r.provider == 'mock' for r in selected_routes) and not fixture_only:
            raise ValueError('Mock and model responses cannot be mixed in an evaluation')
        print(f"Evaluation: {args.suite}   Units: {plan['units']}   Model requests: up to {plan['model_calls']}", flush=True)
        if args.dry_run:
            return 0
        for r in selected_routes:
            if r.provider != 'mock' and not r.model:
                raise ValueError('Every selected model needs a model ID')
            if r.provider in ('openai', 'anthropic') and not os.getenv(r.api_key_env):
                raise ValueError(f'Set {r.api_key_env}')
        if args.timeout <= 0:
            raise ValueError('--timeout must be positive')
        out = (args.output or Path('runs') / (args.suite + '-' + __import__('time').strftime('%Y%m%d-%H%M%S'))).resolve()
        if out.exists():
            raise ValueError('Output directory already exists. Choose a new --output path.')
        out.mkdir(parents=True)
        plan.update({'suite': args.suite, 'split': args.split, 'fixture_only': fixture_only,
                     'models': {alias: {key: value for key, value in asdict(routes.get(alias, route)).items()
                                        if key not in ('api_key_env', 'base_url')} for alias in sorted(aliases)}})
        (out / 'run_config.json').write_text(json.dumps(plan, indent=2) + '\n')
        provider = Provider(route, protocol.Writer(out / 'calls.jsonl'), routes, args.timeout, args.retries)
        try:
            function = getattr(runners, 'run_' + {'policy-update': 'policy_updates'}.get(args.suite, args.suite))
            observations, metrics = function(repo, provider, out, args.limit, args.split)
            writer = protocol.Writer(out / 'observations.jsonl')
            for row in observations:
                writer.append(row)
            if args.suite != 'agentdojo':
                writer = protocol.Writer(out / 'paired_scores.jsonl')
                for row in metrics:
                    writer.append(row)
                metrics = runners.summary(metrics)
            report = {'fixture_only': fixture_only, 'provider_attempts': provider.calls,
                      'failed_calls': provider.errors, 'metrics': metrics,
                      'status': 'completed_with_provider_errors' if provider.errors else 'completed'}
            if args.suite == 'agentdojo' and any(not row.get('protocol_conformant') for row in observations):
                report['status'] = 'completed_with_protocol_errors'
            (out / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
            inspect_results(out)
            print(f'Results: {out}')
            return 0 if report['status'] == 'completed' else 2
        finally:
            provider.close()
    except (ValueError, FileNotFoundError, ImportError) as exc:
        print(f'Setup error: {exc}', file=sys.stderr)
        return 1


def selection(repo, args):
    if args.suite == 'permission':
        pairs = data.paired_graphs(protocol.rows(repo / f'data/permission/{args.split}_provider_graphs.jsonl'), args.limit)
        cells = [graph for pair in pairs for graph in pair]
        aliases = {role['model'] for graph in cells for role in graph['roles']} | {'sonnet_45', 'haiku_45', 'qwen3_32b', 'gemma3_27b'}
        return {'units': len(pairs), 'model_calls': sum(graph['N'] + 4 for graph in cells)}, aliases
    if args.suite == 'assembly':
        groups = runners.groups(protocol.rows(repo / f'data/assembly/{args.split}_artifact_cells.jsonl'), ['scenario_id', 'team_id'], args.limit)
        keys = {(g[0]['scenario_id'], g[0]['team_id']) for g in groups}
        composers = protocol.rows(repo / f'data/assembly/{args.split}_composer_cells.jsonl')
        aliases = {row['model'] for group in groups for row in group} | {row['model'] for row in composers if (row['scenario_id'], row['team_id']) in keys}
        return {'units': len(groups), 'model_calls': len(groups) * 5}, aliases
    if args.suite == 'policy-update':
        groups = runners.groups(protocol.rows(repo / f'data/policy_updates/{args.split}_provider_graphs.jsonl'), ['scenario_id', 'team_id', 'N'], args.limit)
        return {'units': len(groups), 'model_calls': sum(sum(graph['N'] for graph in group) + 2 for group in groups)}, {role['model'] for group in groups for graph in group for role in graph['roles']}
    name = 'confirmation_selected_cells' if args.split == 'confirmation' else 'development_cells'
    groups = runners.groups(protocol.rows(repo / f'data/agentdojo/{name}.jsonl'), ['pair_id', 'model', 'variant'], args.limit)
    return {'units': len(groups), 'model_calls': sum(len(cell['slot_plan']) for group in groups for cell in group)}, {cell['model'] for group in groups for cell in group}


if __name__ == '__main__':
    raise SystemExit(main())
