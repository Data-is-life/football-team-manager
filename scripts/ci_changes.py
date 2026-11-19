"""Select PR test groups conservatively, and verify the required final CI gate."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def select_checks(paths, *, force_full=False):
    paths = tuple(paths)
    if force_full or not paths:
        return {'python': True, 'ui': True}
    selected = {'python': False, 'ui': False}
    for path in paths:
        if path.startswith('.github/'):
            return {'python': True, 'ui': True}
        if path in ('README.md', 'QUICKSTART.md', 'LICENSE', 'LICENSE.md') or path.startswith('docs/'):
            continue
        if path.startswith('app/static/') or (path.startswith('tests/ui_') and path.endswith('.cjs')) or path == 'scripts/run-ui-tests.cjs':
            selected['ui'] = True
            continue
        # Backend changes, Python fixtures, dependencies and unknown paths run both.
        return {'python': True, 'ui': True}
    return selected


def changed_paths(base, head, *, cwd=None):
    # No rename detection: both the removed old path and added new path are checked.
    result = subprocess.check_output(
        ['git', 'diff', '--name-only', '-z', '--no-renames', f'{base}...{head}', '--'], cwd=cwd, stderr=subprocess.PIPE)
    return [os.fsdecode(path) for path in result.split(b'\0') if path]


def verify_results(selected, results, changes_result):
    if changes_result != 'success':
        raise ValueError('Change detection did not succeed')
    for group in ('python', 'ui'):
        if selected[group] not in ('true', 'false'):
            raise ValueError(f'Missing or invalid {group} selection')
        allowed = ('success',) if selected[group] == 'true' else ('success', 'skipped')
        if results[group] not in allowed:
            raise ValueError(f'{group} checks ended with {results[group]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('select', 'verify'))
    parser.add_argument('--force-full', action='store_true')
    args = parser.parse_args()
    if args.action == 'verify':
        verify_results({g:os.environ.get(f'{g.upper()}_SELECTED','') for g in ('python','ui')},
                       {g:os.environ.get(f'{g.upper()}_RESULT','') for g in ('python','ui')},
                       os.environ.get('CHANGES_RESULT',''))
        print('All selected checks passed; unrelated groups were skipped.')
        return
    paths = () if args.force_full else changed_paths(os.environ['BASE_SHA'], os.environ['HEAD_SHA'])
    selected = select_checks(paths, force_full=args.force_full)
    print(json.dumps({'forced_full':args.force_full, 'changed_file_count':None if args.force_full else len(paths), 'checks':selected}))
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            for group, enabled in selected.items():
                output.write(f'{group}={str(enabled).lower()}\n')


if __name__ == '__main__':
    main()
