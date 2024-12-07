import sys
import yaml
import configparser

def add_namespace_selector(doc:dict) -> list[str]:
    return process_ingress_from(doc) + process_egress_to(doc)

def process_ingress_from(doc:dict) -> list[str]:
    paths = []
    for rule_index, rule in enumerate(doc.get('spec', {}).get('ingress', [])):
        for entry_index, entry in enumerate(rule.get('from', [])):
            if 'podSelector' in entry:
                paths.append(f"spec.ingress.{rule_index}.from.{entry_index}.namespaceSelector.matchLabels.[kubernetes.io/metadata.name]")
    return paths

def process_egress_to(doc:dict) -> list[str]:
    paths = []
    for rule_index, rule in enumerate(doc.get('spec', {}).get('egress', [])):
        for entry_index, entry in enumerate(rule.get('to', [])):
            if 'podSelector' in entry:
                paths.append(f"spec.egress.{rule_index}.to.{entry_index}.namespaceSelector.matchLabels.[kubernetes.io/metadata.name]")
    return paths

def spaces(n:int) -> str:
    return ' ' * n

def print_target(offset:int, resource_name:str, paths:list[str], output_stream) -> None:
    if len(paths):
        print(f"{spaces(offset)}- select:", file=output_stream)
        print(f"{spaces(offset)}    kind: NetworkPolicy", file=output_stream)
        print(f"{spaces(offset)}    name: {resource_name}", file=output_stream)
        print(f"{spaces(offset)}  fieldPaths:", file=output_stream)
        for path in paths:
            print(f"{spaces(offset)}    - {path}", file=output_stream)
        print(f"{spaces(offset)}  options:", file=output_stream)
        print(f"{spaces(offset)}    create: true", file=output_stream)

def print_source(offset:int, output_stream, config) -> None:
    print(f"{spaces(offset)}- source:", file=output_stream)
    print(f"{spaces(offset)}    kind: {config['kind']}", file=output_stream)
    print(f"{spaces(offset)}    name: {config['name']}", file=output_stream)
    print(f"{spaces(offset)}    fieldPath: {config['fieldPath']}", file=output_stream)
    print(f"{spaces(offset)}  targets:", file=output_stream)

def process_manifests(input_stream, output_stream, config):
    documents = yaml.safe_load_all(input_stream)
    replacements= {}

    for doc in documents:
        if doc is None or not isinstance(doc, dict):
            continue

        kind = doc.get("kind", "").lower()
        resource_name = doc.get("metadata", {}).get("name", "unknown")

        if kind in ["networkpolicy"]:
            replacements[resource_name] = add_namespace_selector(doc)

    offset = 0
    print_source(offset, output_stream, config)
    for key, value in replacements.items():
        print_target(offset+4, key, value, output_stream)

if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(['default.ini','config.ini'])
    replacement_config = config['replacement']

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(sys.stdin, sys.stdout, replacement_config)
    elif len(sys.argv) == 2:
        input_file = sys.argv[1]
        with open(input_file, 'r') as file:
            process_manifests(file, sys.stdout, replacement_config)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(infile, outfile, replacement_config)
    else:
        print("Usage: python add-nsselector.py [input_file] [output_file]", file=sys.stderr)
