import sys
import yaml
import configparser

def generate_dynamic_label(label_prefix:str, resource_type:str, resource_name:str) -> str:
    if label_prefix: 
        return f"{label_prefix}-{resource_type}-{resource_name}" 
    else: 
        return f"{resource_type}-{resource_name}"

def add_label_to_template(resource:dict, label_key:str, label_value:str) -> None:
    labels = resource.setdefault("spec", {}).setdefault("template", {}).setdefault("metadata", {}).setdefault("labels", {})
    labels[label_key] = label_value

def process_manifests(label_name, label_prefix, input_stream, output_stream) -> None:
    documents = yaml.safe_load_all(input_stream)
    output_documents = []

    for doc in documents:
        if doc is None or not isinstance(doc, dict):
            continue

        kind = doc.get("kind", "").lower()
        resource_name = doc.get("metadata", {}).get("name", "unknown")
        dynamic_label = generate_dynamic_label(label_prefix, kind, resource_name)

        # Add label to metadata if ["metadata"]["labels"] exists
        if "metadata" in doc and "labels" in doc["metadata"]:
            doc["metadata"]["labels"][label_name] = dynamic_label

        # Add label to spec template based on resource type
        if kind in ["deployment", "job"]:
            add_label_to_template(doc, label_name, dynamic_label)

        # Special handling for CronJob (nested JobTemplate)
        elif kind == "cronjob":
            if "spec" in doc and "jobTemplate" in doc["spec"]:
                add_label_to_template(doc["spec"]["jobTemplate"], label_name, dynamic_label)

        elif kind == "mongodbcommunity":
            if "spec" in doc and "statefulSet" in doc["spec"]:
                add_label_to_template(doc["spec"]["statefulSet"], label_name, dynamic_label)

        output_documents.append(doc)

    yaml.dump_all(output_documents, output_stream, default_flow_style=False)


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read(['default.ini','config.ini'])
    label_config = config['label']
    name= label_config['name']
    prefix = label_config['prefix']

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(name, prefix, sys.stdin, sys.stdout)
    elif len(sys.argv) == 2:
        input_file = sys.argv[1]
        with open(input_file, 'r') as file:
            process_manifests(name, prefix, file, sys.stdout)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(name, prefix, infile, outfile)
    else:
        print("Usage: python add-label.py [input_file] [output_file]", file=sys.stderr)
