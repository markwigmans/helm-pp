# Helm Chart Post-Processing Scripts

## Overview

This repository contains Python scripts designed to post-process the output of Helm charts, ensuring compliance with specific rules. The scripts provide functionality to:

1. Add a required label to every resource
2. Add a NamespaceSelector to NetworkPolicy resources
3. Retrieve images

## Scripts

### 1. Add Required Label (`add-label.py`)

This script adds a specified label to every resource in the Helm chart output.

#### Functionality:
- Adds the label to `metadata/labels` if it exists
- For resources that support templates (e.g., 'Deployment'), updates `template/metadata/labels` as well

#### Usage:
````console
python add-label.py [input_file] [output_file]
````

- If no `input_file` is provided, the script reads from stdin
- If no `output_file` is specified, the script uses stdout

If only 1 file is given, it will be used as `output_file`. 

#### Configuration:
The script uses `config.ini` for configuration:

| Section | Key    | Description            | Default |
|---------|--------|------------------------|---------|
| label   | name   | Name of label          | dname   |

### 2. Add Required NamespaceSelector (`add-nsselector.py`)

This script generates a [Kustomize](https://kustomize.io/) replacement file to ensure that every NetworkPolicy with a from/to podSelector includes a NamespaceSelector.

#### Usage:

````console
python add-nsselector.py [input_file] [output_file]
````
- If no `input_file` is provided, the script reads from stdin
- If no `output_file` is specified, the script uses stdout

If only 1 file is given, it will be used as `output_file`. 

#### Configuration:
The script uses `config.ini` for configuration:

| Section     | Key       | Description               | Default            |
|-------------|-----------|---------------------------|--------------------|
| nsselector  | kind      | Kind of source field      | Deployment         |
| nsselector  | name      | Name of source field      | api                |
| nsselector  | fieldPath | FieldPath of source field | metadata.namespace |

### 3. Retrieve Image Descriptions (`get-image.py`)

Retrieve the image descriptions as mentioned in the deployment files as well dynamic references via environment variables.

#### Usage:

````console
python get-image.py [input_file] [output_file]
````
- If no `input_file` is provided, the script reads from stdin
- If no `output_file` is specified, the script uses stdout

If only 1 file is given, it will be used as `output_file`. 

## Installation

````console
pip install -r requirements.txt
````

## Requirements

- [Python 3.x](https://www.python.org/)
- [Helm](https://helm.sh/) (for generating the initial chart output)
- [Kustomize](https://kustomize.io/) (for applying the NamespaceSelector replacements)
