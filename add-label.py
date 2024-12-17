"""
Add Required labels to a given K8s resource file
"""
import logging
import sys
from configparser import ConfigParser
from copy import deepcopy
from datetime import datetime

import yaml

# Configure the logger
logging.basicConfig(level=logging.INFO)


def generate_dynamic_label(resource_type: str, resource_name: str) -> str:
    return f"{resource_type}-{resource_name}"


def add_label(resource: dict, key: str, value: str) -> None:
    # add value if key does not exist
    resource.setdefault(key, value)


def add_label_to_template(resource: dict, key: str, value: str) -> None:
    add_label(resource.get("spec", {}).get("template", {}).get("metadata", {}).setdefault("labels", {}), key, value)


def remove_null_values(data):
    """Remove null values to prevent 'null' strings in the final result"""
    if isinstance(data, dict):
        return {k: remove_null_values(v) for k, v in data.items() if v is not None}
    elif isinstance(data, list):
        return [remove_null_values(item) for item in data if item is not None]
    else:
        return data


def create_key_value(match: tuple[str, str]) -> str:
    return f"{match[0]}:{match[1]}"


def add_to_dict(dictionary: dict, match: tuple[str, str], label) -> None:
    key = create_key_value(match)
    dictionary.setdefault(key, []).append(label)


def add_matching_labels(matching_dict: dict, resource: dict, label: str) -> None:
    kind = resource.get("kind", "").lower()

    match kind:
        case "deployment":
            labels = resource.get("spec", {}).get("selector", {}).get("matchLabels", {})
        case "job":
            labels = resource.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
        case "cronjob":
            labels = resource.get("spec", {}).get("jobTemplate", {}).get("spec", {}).get("template", {}).get("metadata",
                                                                                                             {}).get(
                "labels", {})
        case _:
            labels = resource.get("spec", {}).get("statefulSet", {}).get("spec", {}).get("template", {}).get("metadata",
                                                                                                             {}).get(
                "labels", {})

    for key, value in labels.items():
        logging.debug(f"add_matching_labels : {label} : {key}:{value}")
        add_to_dict(matching_dict, (key, value), label)


def create_rules(entry: dict, matching: list[str], label_name: str) -> list[dict]:
    if matching:
        result = []
        for match in matching:
            copy = deepcopy(entry)
            add_label(copy.get("podSelector", {}).setdefault("matchLabels", {}), label_name, match)
            result.append(copy)
        return result
    else:
        logging.warning(f"create_rules : {matching} not found for {entry}")
        return [deepcopy(entry)]


def create_pod_selector_rules(entry: dict, matching_labels: dict, label_name: str) -> list[dict]:
    """add pod selector rules to a given entry with podSelector"""
    result = []
    labels = entry.get("podSelector", {}).get("matchLabels", {})
    for key, value in labels.items():
        matching = matching_labels.get(create_key_value((key, value)), [])
        result.extend(create_rules(entry, matching, label_name))
    return result


def process_ns_ingress_from(doc: dict, matching_labels: dict, label_name: str) -> None:
    if doc.get('spec', {}).get('ingress', []):
        for rule in doc.get('spec', {}).get('ingress', []):
            elements = []
            for entry in rule.get('from', []):
                if 'podSelector' in entry:
                    elements.extend(create_pod_selector_rules(entry, matching_labels, label_name))
                else:
                    elements.append(entry)
            rule['from'] = elements


def process_ns_egress_to(doc: dict, matching_labels: dict, label_name: str) -> None:
    if doc.get('spec', {}).get('egress', []):
        for rule in doc.get('spec', {}).get('egress', []):
            elements = []
            for entry in rule.get('to', []):
                if 'podSelector' in entry:
                    elements.extend(create_pod_selector_rules(entry, matching_labels, label_name))
                else:
                    elements.append(entry)
            rule['to'] = elements


def update_network_policy(doc: dict, matching_labels: dict, label_name: str) -> None:
    process_ns_ingress_from(doc, matching_labels, label_name)
    process_ns_egress_to(doc, matching_labels, label_name)


def process_manifests(label_name: str, extra_labels: dict, input_stream, output_stream) -> None:
    documents = yaml.safe_load_all(input_stream)
    step1_documents = []
    matching_labels = {}

    # step 1 - get matching labels / add dname label
    for doc in filter(lambda x: isinstance(x, dict), documents):
        kind = doc.get("kind", "").lower()
        resource_name = doc.get("metadata", {}).get("name", "unknown")
        dynamic_label = generate_dynamic_label(kind, resource_name)

        # Add label to metadata if ["metadata"]["labels"] exists
        if "labels" in doc.get("metadata", {}):
            add_label(doc["metadata"]["labels"], label_name, dynamic_label)

        # handle deployment template case
        if "template" in doc.get("spec", {}):
            add_label_to_template(doc, label_name, dynamic_label)
            add_matching_labels(matching_labels, doc, dynamic_label)

        # handle template if part of another structure
        for key in ("jobTemplate", "statefulSet"):
            if key in doc.get("spec", {}):
                add_label_to_template(doc.get("spec", {}).get(key), label_name, dynamic_label)
                add_matching_labels(matching_labels, doc, dynamic_label)
        step1_documents.append(doc)

    # step 2 - update network policies
    step2_documents = []
    # add the extra labels. If in both, then use the 'matching_labels' version
    matching_labels = extra_labels | matching_labels
    for doc in filter(lambda x: isinstance(x, dict), step1_documents):
        kind = doc.get("kind", "").lower()
        if kind == "networkpolicy":
            update_network_policy(doc, matching_labels, label_name)
        step2_documents.append(doc)

    cleaned_data = remove_null_values(step2_documents)
    print(f"#\n# GENERATED by 'add-label.py' at {datetime.now().strftime('%H:%M:%S')}\n#", file=output_stream)
    yaml.dump_all(cleaned_data, output_stream, default_flow_style=False)


def main():
    config = ConfigParser()
    config.read(['default.ini', 'config.ini'])
    label_config = config['label']
    name = label_config['name']

    extra_labels = {}
    for section in config.sections():
        if section.startswith('label.match.'):
            add_to_dict(extra_labels,
                        (config[section]['label'], config[section]['value']),
                        config[section]['extra.label.value'])

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(name, extra_labels, sys.stdin, sys.stdout)
    elif len(sys.argv) == 2:
        output_file = sys.argv[1]
        with open(output_file, 'w') as file:
            process_manifests(name, extra_labels, sys.stdin, file)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(name, extra_labels, infile, outfile)
    else:
        print("Usage: python add-label.py [input_file] [output_file]", file=sys.stderr)


if __name__ == "__main__":
    main()
