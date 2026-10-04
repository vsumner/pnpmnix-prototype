"""Prepare a reviewed frozen profile, restore matching dependencies, then use stock pnpm."""
import argparse
import json
from pathlib import Path
import sys

if sys.flags.optimize:
    raise SystemExit('Verification requires Python without -O/PYTHONOPTIMIZE.')
sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent/'scripts'))
from flow import PnpmCommandError, host, locked, prepare, restore, rollback, stock


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command',required=True)
    q = sub.add_parser('prepare',help='strict Nix preparation with explicit reviewed profile')
    q.add_argument('--profile',required=True,choices=['vite','fixture-a','fixture-b','fixture-c','hono','hono-experiment'])
    q.add_argument('--output',required=True,help='new retained preparation directory outside source')
    q = sub.add_parser('restore',help='verify match and activate private dependency copies')
    q.add_argument('--prepared',required=True,help='prepared.json from prepare')
    q.add_argument('--run-checkout-hooks',action='store_true',help='run the profile\'s explicit checkout hooks; otherwise report them pending')
    for name in ['restore','pnpm','recover']:
        if name != 'restore': q = sub.add_parser(name)
        q.add_argument('--checkout',required=True)
        q.add_argument('--state',required=True,help='private state directory outside checkout and source')
        if name == 'pnpm':
            q.add_argument('--offline',action='store_true',help='also inherited by automatic installs')
            q.add_argument('args',nargs=argparse.REMAINDER,help='stock pnpm arguments after --')
    args = p.parse_args()
    if args.command == 'prepare': result = prepare(args.profile,args.output)
    else:
        host(check_daemon=False)
        if args.command == 'restore': result = restore(args.prepared,args.checkout,args.state,args.run_checkout_hooks)
        elif args.command == 'pnpm':
            argv = args.args[1:] if args.args and args.args[0] == '--' else args.args
            try: result = stock(args.checkout,args.state,argv,args.offline)
            except PnpmCommandError as error: result = error.result
            # Native stdout/stderr retain their streams; the wrapper receipt is
            # diagnostic output, including drift after successful mutations.
            print(json.dumps(result,indent=2),file=sys.stderr)
            return result['exit_code'] if result['exit_code'] >= 0 else 128-result['exit_code']
        else:
            with locked(args.checkout,args.state) as (checkout,state): result = rollback(checkout,state)
    if args.command == 'restore':
        result = {k:result[k] for k in ['profile','checkout','store','checkout_hooks','lifecycle','attempt']} | {
            'dependency_directories':len(result['owned']),'receipt':str(Path(args.state).resolve()/'active.json')}
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    try: raise SystemExit(main())
    except (ValueError, OSError) as error: raise SystemExit(str(error))
