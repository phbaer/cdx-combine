import json
from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.output.json import JsonV1Dot5
from cyclonedx.schema import OutputFormat, SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from cyclonedx.exception import MissingOptionalDependencyException
import sys
import glob
import logging


class CDX_Combine:
    def run(self, args):
        logging.basicConfig(level=logging.INFO)

        name: str = args.name
        version: str = args.version
        ref = name.lower().replace(' ', '_')
        files = args.files
        
        logging.info(f'Generating SBOM for {name} {version} from {", ".join(files)}...')

        boms = []
        for file in files:
            for file in glob.glob(file):
                logging.info(f'Loading {file}...')
                with open(file, 'r') as input_file:
                    boms.append(Bom.from_json(data=json.loads(input_file.read())))

        new_bom = Bom()
        new_bom.metadata.component = root_component = Component(name=name, type=ComponentType.APPLICATION, licenses=[], bom_ref=ref, version=version)

        for bom in boms:
            bom_component = bom.metadata.component
            bom_ref = bom_component.bom_ref.value
            logging.info(f'Processing {bom_ref}...')

            new_bom.components.add(bom_component)
            for component in bom.components:
                new_bom.components.add(component)
            
            dependencies = []
            for dependency in bom.dependencies:
                dependency.bom_ref = dependency.ref
                new_dependency_list = []
                for inner_dependency in dependency.dependencies:
                    inner_dependency.bom_ref = inner_dependency.ref
                    new_dependency_list.append(inner_dependency)
                if len(new_dependency_list) > 0:
                    new_bom.register_dependency(dependency, new_dependency_list)
            new_bom.register_dependency(bom_component, dependencies)
            new_bom.register_dependency(root_component, [bom_component])

        my_json_outputter: 'JsonOutputter' = JsonV1Dot5(new_bom)
        serialized_json = my_json_outputter.output_as_string(indent=2)
        my_json_validator = JsonStrictValidator(SchemaVersion.V1_5)
        try:
            validation_errors = my_json_validator.validate_str(serialized_json)
            if validation_errors:
                print('JSON invalid', 'ValidationError:', repr(validation_errors), sep='\n', file=sys.stderr)
                #sys.exit(2)
            #print('JSON valid')
        except MissingOptionalDependencyException as error:
            print('JSON-validation was skipped due to', error)
            
        with open('cyclonedx.json', 'w') as f:
            f.write(serialized_json)

