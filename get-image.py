"""
Create a list of images from a given K8s resource file
"""
import re
import sys
from configparser import ConfigParser
from datetime import datetime

import yaml


def get_images(resource: dict) -> list[str]:
    return _get_images_from_template(resource) + _get_images_from_env(resource)


def _get_images_from_template(resource: dict) -> list[str]:
    spec = resource.get("spec", {}).get("template", {}).get("spec", {})
    containers = spec.get("containers", []) + spec.get("initContainers", [])
    return [container["image"] for container in containers if "image" in container]


def _get_images_from_env(resource: dict) -> list[str]:
    pattern = r'(.*)__(?:IMAGE|TAG)$'
    matched_items = {}
    containers = resource.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])

    for container in containers:
        for env in container.get("env", []):
            image_key = next(
                (re.match(pattern, v).group(1) for k, v in env.items() if isinstance(v, str) and re.match(pattern, v)),
                '')
            if image_key:
                _insert_or_append(matched_items, image_key, next(v for k, v in env.items() if k != 'name'))

    return [':'.join(sublist) for sublist in matched_items.values()]


def _insert_or_append(dictionary, key, value) -> None:
    dictionary[key] = [dictionary[key], value] if key in dictionary else value
    if isinstance(dictionary[key], list) and len(dictionary[key]) > 2:
        dictionary[key] = dictionary[key][0:1] + [':'.join(dictionary[key][1:])]


def extract_path_and_tag(image_reference: str) -> tuple[str, str]:
    # Remove the host and port if present
    path_and_tag = image_reference.split('/', 1)[-1]

    # Split the path and tag
    parts = path_and_tag.rsplit(':', 1)

    path = parts[0]
    tag = parts[1] if len(parts) > 1 else 'latest'

    return path, tag


def process_manifests(repo: str, input_stream, output_stream) -> None:
    documents = yaml.safe_load_all(input_stream)
    images = set()

    for doc in filter(lambda x: isinstance(x, dict) and "spec" in x, documents):
        images.update(get_images(doc))
        for key in ("jobTemplate", "statefulSet"):
            if key in doc["spec"]:
                images.update(get_images(doc["spec"].get(key, doc)))

    print(f"#\n# GENERATED by 'get-image.py' at {datetime.now().strftime('%H:%M:%S')}\n#", file=output_stream)

    # create the list of images
    extract = [f"{repo}/{path}:{tag}" for path, tag in (extract_path_and_tag(ref) for ref in images)]
    merged = [f"{a} {b}" for a, b in zip(images, extract) if a != b]

    print(*sorted(merged), sep='\n', file=output_stream)


def main():
    config = ConfigParser()
    config.read(['default.ini', 'config.ini'])
    image_config = config['image']
    repo = image_config['repo']

    # Check if a file path is provided as an argument
    if len(sys.argv) == 1:
        process_manifests(repo, sys.stdin, sys.stdout)
    elif len(sys.argv) == 2:
        output_file = sys.argv[1]
        with open(output_file, 'w') as file:
            process_manifests(repo, sys.stdin, file)
    elif len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
        with open(input_file, 'r') as infile, open(output_file, 'w') as outfile:
            process_manifests(repo, infile, outfile)
    else:
        print("Usage: python add-label.py [input_file] [output_file]", file=sys.stderr)


if __name__ == "__main__":
    main()
