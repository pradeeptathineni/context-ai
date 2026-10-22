"""Show file-scoped project and synthetic private guidance without a provider."""

import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from context_ai import apply, resolve
from context_delivery import prepare


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        project, private = root / 'project', root / 'custom'
        project.mkdir()
        private.mkdir()
        (project / 'AGENTS.md').write_text('Preserve the public API.\n')
        (private / 'README.md').write_text('Synthetic personal defaults.\n')
        (private / 'voice.md').write_text('Use short natural sentences; preserve facts.\n')
        (private / 'guidance.yaml').write_text(json.dumps({'schema_version': 1, 'rules': [
            {'id': 'voice', 'path': 'voice.md', 'globs': '**/*.md', 'topic': 'voice'}]}))
        lock, files = resolve([], project, 'both')
        apply(project, lock, files)
        (project / 'docs.md').write_text('Start with what the reader can do.\n')
        (project / 'api.md').write_text('Keep the typed API compatible.\n')
        (project / '.context-ai/guidance.yaml').write_text(json.dumps({'schema_version': 1, 'rules': [
            {'id': 'docs', 'path': 'docs.md', 'directory': 'docs'},
            {'id': 'api', 'path': 'api.md', 'globs': '**/*.py'}]}))
        for scope in ('docs/guide.md', 'src/api.py'):
            result = prepare(project, 'codex', task_files=(scope,), private_root=private)
            print('\nTask:', scope)
            print(result['context'])
            print('Project decisions:', json.dumps(result['public_receipt']['guidance']))


if __name__ == '__main__':
    main()
