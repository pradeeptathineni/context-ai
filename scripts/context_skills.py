#!/usr/bin/env python3
"""Agent Skills package metadata checks at Context's acquisition and delivery boundary.

Adapted from agentskills/agentskills@69ef37e9424c0a7ea9dd2293b559e43ec8176379
skills-ref/src/skills_ref/{validator,parser,errors}.py, Copyright the Agent Skills
authors, licensed under the Apache License 2.0 (sourced/agentskills/LICENSE).

Changes from upstream (2026-10-21, Context): frontmatter is parsed with Context's
bounded safe YAML loader (duplicate/non-string keys, aliases and object tags fail)
instead of strictyaml, so non-string scalars are rejected rather than coerced;
the closing delimiter must be its own line; SKILL.md, package file count and bytes
are bounded; only an exact SKILL.md entry is accepted; symlinks, active instruction
filenames and allowed-tools pre-approval are refused for Context delivery. The
CLI, prompt generator and SkillProperties model are not included.
"""
from pathlib import Path
import re
import unicodedata

import yaml

from context_ai import Invalid, digest, encoded, parse_yaml

MAX_SKILL_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024
MAX_COMPATIBILITY_LENGTH = 500
# Context bounds; the specification recommends a short SKILL.md body.
MAX_SKILL_BYTES = 64 * 1024
MAX_PACKAGE_FILES = 32
MAX_PACKAGE_BYTES = 512 * 1024

ALLOWED_FIELDS = {'name', 'description', 'license', 'allowed-tools', 'metadata', 'compatibility'}
ACTIVE_INSTRUCTIONS = {'agents.md', 'agents.override.md', 'claude.md', 'gemini.md'}
FRONTMATTER = re.compile(r'---\r?\n(.*?)^---[ \t]*(?:\r?\n|\Z)', re.S | re.M)


def parse(data):
    """Return (metadata, body) from exact SKILL.md bytes; raise Invalid on any parse failure."""
    if len(data) > MAX_SKILL_BYTES:
        raise Invalid(f'SKILL.md exceeds {MAX_SKILL_BYTES} bytes ({len(data)})')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise Invalid('SKILL.md is not UTF-8') from None
    if not text.startswith('---'):
        raise Invalid('SKILL.md must start with YAML frontmatter (---)')
    match = FRONTMATTER.match(text)
    if not match:
        raise Invalid('SKILL.md frontmatter not properly closed with ---')
    try:
        metadata = parse_yaml(match.group(1))
    except yaml.YAMLError as error:
        raise Invalid('Invalid YAML in frontmatter: ' + str(error).splitlines()[0]) from None
    if not isinstance(metadata, dict):
        raise Invalid('SKILL.md frontmatter must be a YAML mapping')
    return metadata, text[match.end():].strip()


def _name(name, expected):
    if not isinstance(name, str) or not name.strip():
        return ["Field 'name' must be a non-empty string"]
    errors = []
    name = unicodedata.normalize('NFKC', name.strip())
    if len(name) > MAX_SKILL_NAME_LENGTH:
        errors.append(f"Skill name '{name}' exceeds {MAX_SKILL_NAME_LENGTH} character limit ({len(name)} chars)")
    if name != name.lower():
        errors.append(f"Skill name '{name}' must be lowercase")
    if name.startswith('-') or name.endswith('-'):
        errors.append('Skill name cannot start or end with a hyphen')
    if '--' in name:
        errors.append('Skill name cannot contain consecutive hyphens')
    if not all(c.isalnum() or c == '-' for c in name):
        errors.append(f"Skill name '{name}' contains invalid characters. Only letters, digits, and hyphens are allowed.")
    if expected is not None and unicodedata.normalize('NFKC', expected) != name:
        errors.append(f"Directory name '{expected}' must match skill name '{name}'")
    return errors


def _text(field, value, limit, required=False):
    if not isinstance(value, str) or (required and not value.strip()):
        return [f"Field '{field}' must be a " + ('non-empty ' if required else '') + 'string']
    if len(value) > limit:
        return [f'{field.capitalize()} exceeds {limit} character limit ({len(value)} chars)']
    return []


def validate_metadata(metadata, expected_name=None):
    """Specification checks on parsed frontmatter. An empty list means valid."""
    errors = []
    extra = set(metadata) - ALLOWED_FIELDS
    if extra:
        errors.append(f"Unexpected fields in frontmatter: {', '.join(sorted(extra))}. "
                      f'Only {sorted(ALLOWED_FIELDS)} are allowed.')
    if 'name' not in metadata:
        errors.append('Missing required field in frontmatter: name')
    else:
        errors.extend(_name(metadata['name'], expected_name))
    if 'description' not in metadata:
        errors.append('Missing required field in frontmatter: description')
    else:
        errors.extend(_text('description', metadata['description'], MAX_DESCRIPTION_LENGTH, required=True))
    if 'compatibility' in metadata:
        errors.extend(_text('compatibility', metadata['compatibility'], MAX_COMPATIBILITY_LENGTH))
    if 'license' in metadata and not isinstance(metadata['license'], str):
        errors.append("Field 'license' must be a string")
    if 'allowed-tools' in metadata and not isinstance(metadata['allowed-tools'], str):
        errors.append("Field 'allowed-tools' must be a string")
    if 'metadata' in metadata:
        value = metadata['metadata']
        if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
            errors.append("Field 'metadata' must map strings to quoted strings")
    return errors


def delivery_errors(metadata):
    """Context policy beyond the specification: a package cannot pre-approve tools."""
    if 'allowed-tools' in metadata:
        return ['allowed-tools pre-approval is not delivered by Context; review tool authority natively']
    return []


def check_entry(data, expected_name):
    """All errors for one SKILL.md entry, including delivery policy."""
    try:
        metadata, _ = parse(data)
    except Invalid as error:
        return [str(error)]
    return validate_metadata(metadata, expected_name) + delivery_errors(metadata)


def require_entry(data, expected_name, label):
    errors = check_entry(data, expected_name)
    if errors:
        raise Invalid('invalid skill package ' + label + ': ' + '; '.join(errors))
    return parse(data)[0]


def check_package(directory):
    """Read-only acquisition check of one candidate package directory."""
    directory = Path(directory)
    report = {'schema_version': 1, 'package': str(directory), 'valid': False, 'errors': [], 'files': {},
              'authority': 'Validation only: nothing is copied, installed, executed or activated.'}
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir():
        report['errors'].append('--package needs an existing absolute non-symlink directory')
        return report
    total, paths = 0, []
    for path in sorted(directory.rglob('*')):
        rel = path.relative_to(directory).as_posix()
        if path.is_symlink():
            report['errors'].append('symlink in package: ' + rel)
        elif path.is_file():
            paths.append((rel, path))
            if path.name.casefold() in ACTIVE_INSTRUCTIONS:
                report['errors'].append('active instruction filename in package: ' + rel)
        elif not path.is_dir():
            report['errors'].append('unsupported file type in package: ' + rel)
        if len(paths) > MAX_PACKAGE_FILES:
            report['errors'].append(f'package exceeds {MAX_PACKAGE_FILES} files')
            return report
    for rel, path in paths:
        size = path.stat().st_size
        total += size
        if total > MAX_PACKAGE_BYTES:
            report['errors'].append(f'package exceeds {MAX_PACKAGE_BYTES} bytes')
            return report
        report['files'][rel] = digest(path.read_bytes())
    # Hosts discover the exact SKILL.md name; a case-folded match is not accepted.
    if 'SKILL.md' not in {rel for rel, _ in paths}:
        report['errors'].append('Missing required file: SKILL.md')
        return report
    data = (directory / 'SKILL.md').read_bytes()
    report['errors'].extend(check_entry(data, directory.name))
    if not report['errors']:
        metadata, body = parse(data)
        report.update(valid=True, name=metadata['name'], description=metadata['description'],
                      body_bytes=len(body.encode()), package_sha256=digest(encoded(report['files'])))
    return report
