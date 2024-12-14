import sys
from configparser import ConfigParser
from datetime import datetime

import yaml


def process_ns_selector(doc: dict) -> dict:
    return to_target_dict(doc, process_ns_ingress_from(doc) + process_ns_egress_to(doc))


def process_ns_ingress_from(doc: dict) -> list[str]:
    paths = []

    # Check if spec.ingress is non-empty
    if not doc.get('spec', {}).get('ingress', []):
        return paths  # Return empty list

    for rule_index, rule in enumerate(doc.get('spec', {}).get('ingress', [])):
        for entry_index, entry in enumerate(rule.get('from', [])):
            if not entry.get('namespaceSelector', {}).get('matchLabels', []):
                if 'podSelector' in entry:
                    paths.append(
                        f"spec.ingress.{rule_index}.from.{entry_index}.namespaceSelector.matchLabels.[kubernetes.io/metadata.name]")
    return paths


def process_ns_egress_to(doc: dict) -> list[str]:
    paths = []

    # Check if spec.egress is non-empty
    if not doc.get('spec', {}).get('egress', []):
        return paths  # Return empty list

    for rule_index, rule in enumerate(doc.get('spec', {}).get('egress', [])):
        for entry_index, entry in enumerate(rule.get('to', [])):
            if not entry.get('namespaceSelector', {}).get('matchLabels', []):
                if 'podSelector' in entry:
                    paths.append(
                        f"spec.egress.{rule_index}.to.{entry_index}.namespaceSelector.matchLabels.[kubernetes.io/metadata.name]")
    return paths


def to_target_dict(doc: dict, paths: list[str]) -> dict:
    if paths:
        return {'target': doc, 'fieldPaths': paths}
    else:
        return {}


def process_ipblock_selector(doc: dict, match: str) -> dict:
    return to_target_dict(doc, process_ipblock_ingress_from(doc, match) + process_ipblock_egress_to(doc, match))


def process_ipblock_ingress_from(doc: dict, match: str) -> list[str]:
    paths = []

    # Check if spec.egress is non-empty
    if not doc.get('spec', {}).get('ingress', []):
        return paths  # Return empty list

    for rule_index, rule in enumerate(doc.get('spec', {}).get('ingress', [])):
        for entry_index, entry in enumerate(rule.get('from', [])):
            if 'ipBlock' in entry:
                cidr = entry.get("ipBlock", {}).get("cidr", "")
                if cidr == match:
                    paths.append(f"spec.ingress.{rule_index}.from.{entry_index}.ipBlock.cidr")
    return paths


def process_ipblock_egress_to(doc: dict, match: str) -> list[str]:
    paths = []

    # Check if spec.egress is non-empty
    if not doc.get('spec', {}).get('egress', []):
        return paths  # Return empty list

    for rule_index, rule in enumerate(doc.get('spec', {}).get('egress', [])):
        for entry_index, entry in enumerate(rule.get('to', [])):
            if 'ipBlock' in entry:
                cidr = entry.get("ipBlock", {}).get("cidr", "")
                if cidr == match:
                    paths.append(f"spec.egress.{rule_index}.to.{entry_index}.ipBlock.cidr")
    return paths


def spaces(n: int) -> str:
    return ' ' * n


def print_target(offset: int, resource_name: str, paths: list[str], output_stream, options) -> None:
    print(f"{spaces(offset)}- select:", file=output_stream)
    print(f"{spaces(offset)}    kind: NetworkPolicy", file=output_stream)
    print(f"{spaces(offset)}    name: {resource_name}", file=output_stream)
    print(f"{spaces(offset)}  fieldPaths:", file=output_stream)
    for path in paths:
        print(f"{spaces(offset)}    - {path}", file=output_stream)
    if options:
        print(f"{spaces(offset)}  options:", file=output_stream)
        print(f"{spaces(offset)}    create: true", file=output_stream)


def print_source(offset: int, output_stream, source: dict) -> None:
    print(f"{spaces(offset)}- source:", file=output_stream)
    print(f"{spaces(offset)}    kind: {source['kind']}", file=output_stream)
    print(f"{spaces(offset)}    name: {source['name']}", file=output_stream)
    print(f"{spaces(offset)}    fieldPath: {source['fieldpath']}", file=output_stream)
    print(f"{spaces(offset)}  targets:", file=output_stream)


def create_key_from_dict(dict_key):
    if not isinstance(dict_key, dict) or 'kind' not in dict_key or 'name' not in dict_key:
        raise ValueError("Input must be a dictionary with 'kind' and 'name' fields")
    return f"{dict_key['kind']}:{dict_key['name']}"


def add_to_dict(dictionary: dict, dict_key: dict, value: dict, options) -> None:
    if value:
        key = create_key_from_dict(dict_key)
        if key not in dictionary:
            dictionary[key] = {'source': dict_key, 'targets': [value], 'options': options}
        else:
            dictionary[key]['targets'].append(value)


def process_manifests(input_stream, output_stream, ns_config, ipblock_configs):
    documents = yaml.safe_load_all(input_stream)
    sources = {}

    for doc in filter(lambda x: isinstance(x, dict) and x.get("kind", "").lower() == "networkpolicy", documents):
        add_to_dict(sources, ns_config, process_ns_selector(doc), True)
        for config in ipblock_configs:
            add_to_dict(sources, config, process_ipblock_selector(doc, config['field']), False)

    print(f"#\n# GENERATED by 'update-np.py' at {datetime.now().strftime('%H:%M:%S')}\n#", file=output_stream)
    for source_key in sources:
        source = sources[source_key]
        print_source(0, output_stream, source['source'])
        for targets in source['targets']:
            resource_name = targets['target'].get("metadata", {}).get("name", "unknown")
            print_target(4, resource_name, targets['fieldPaths'], output_stream, source['options'])


def main():
    config = ConfigParser()
    config.read(['default.ini', 'config.ini'])

    ipblocks = []
    for section in config.sections():
        if section.startswith('ipblock.'):
            ipblocks.append(dict(config[section]))

    nsselector_config = dict(config['nsselector'])

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(sys.stdin, sys.stdout, nsselector_config, ipblocks)
    elif len(sys.argv) == 2:
        output_file = sys.argv[1]
        with open(output_file, 'w') as file:
            process_manifests(sys.stdin, file, nsselector_config, ipblocks)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(infile, outfile, nsselector_config, ipblocks)
    else:
        print("Usage: python update-np.py [input_file] [output_file]", file=sys.stderr)


if __name__ == "__main__":
    main()
