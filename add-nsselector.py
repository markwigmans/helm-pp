import sys
import yaml
import configparser

def add_namespace_selector(doc:dict) -> list[str]:
    return process_ingress_from(doc) + process_egress_to(doc)

def process_ingress_from(doc:dict) -> list[str]:
    paths = []

    # Check if spec.ingress is non-empty
    if not doc.get('spec', {}).get('ingress', []):
        return paths  # Return empty list

    for rule_index, rule in enumerate(doc.get('spec', {}).get('ingress', [])):
        for entry_index, entry in enumerate(rule.get('from', [])):
            if 'podSelector' in entry:
                paths.append(f"spec.ingress.{rule_index}.from.{entry_index}.namespaceSelector.matchLabels.[kubernetes.io/metadata.name]")
    return paths

def process_egress_to(doc:dict) -> list[str]:
    paths = []

    # Check if spec.egress is non-empty
    if not doc.get('spec', {}).get('egress', []):
        return paths  # Return empty list

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
    replacements = {
        doc.get("metadata", {}).get("name", "unknown"): add_namespace_selector(doc)
        for doc in filter(lambda x: isinstance(x, dict) and x.get("kind", "").lower() == "networkpolicy", documents)
    }

    print_source(0, output_stream, config)
    for key, value in replacements.items():
        print_target(4, key, value, output_stream)

def main():
    config = configparser.ConfigParser()
    config.read(['default.ini','config.ini'])
    nsselector_config = config['nsselector']

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(sys.stdin, sys.stdout, nsselector_config)
    elif len(sys.argv) == 2:
        output_file = sys.argv[1]
        with open(output_file, 'w') as file:
            process_manifests(sys.stdin, file, nsselector_config)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(infile, outfile, nsselector_config)
    else:
        print("Usage: python add-nsselector.py [input_file] [output_file]", file=sys.stderr)

if __name__ == "__main__":
    main()
