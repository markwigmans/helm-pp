import sys
import yaml
import configparser

def generate_dynamic_label(resource_type:str, resource_name:str) -> str:
        return f"{resource_type}-{resource_name}"

def add_label_to_template(resource: dict, label_key: str, label_value: str) -> None:
    resource.get("spec", {}).get("template", {}).get("metadata", {}).setdefault("labels", {})[label_key] = label_value

def process_manifests(label_name, input_stream, output_stream) -> None:
    documents = yaml.safe_load_all(input_stream)
    output_documents = []

    for doc in filter(lambda x: isinstance(x, dict), documents):
        kind = doc.get("kind", "").lower()
        resource_name = doc.get("metadata", {}).get("name", "unknown")
        dynamic_label = generate_dynamic_label(kind, resource_name)

        # Add label to metadata if ["metadata"]["labels"] exists
        if "labels" in doc.get("metadata", {}):
            doc["metadata"]["labels"][label_name] = dynamic_label

        # Add label to spec template
        if "template" in doc.get("spec", {}):
            add_label_to_template(doc, label_name, dynamic_label)

        # handle template if part of another structure
        for key in ("jobTemplate", "statefulSet"):
            if key in doc.get("spec", {}):
                add_label_to_template(doc["spec"].get(key, doc), label_name, dynamic_label)

        output_documents.append(doc)

    yaml.dump_all(output_documents, output_stream, default_flow_style=False)

def main():
    config = configparser.ConfigParser()
    config.read(['default.ini','config.ini'])
    label_config = config['label']
    name= label_config['name']

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(name, sys.stdin, sys.stdout)
    elif len(sys.argv) == 2:
        output_file = sys.argv[1]
        with open(output_file, 'w') as file:
            process_manifests(name, sys.stdin, file)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(name, infile, outfile)
    else:
        print("Usage: python add-label.py [input_file] [output_file]", file=sys.stderr)

if __name__ == "__main__":
    main()
