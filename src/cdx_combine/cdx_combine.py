import json
from cyclonedx.model.bom import Bom
from cyclonedx.model.bom_ref import BomRef
from cyclonedx.model.component import Component, ComponentType
from cyclonedx.model.dependency import Dependency
from cyclonedx.output.json import JsonV1Dot5
from cyclonedx.schema import SchemaVersion
from cyclonedx.validation.json import JsonStrictValidator
from cyclonedx.exception import MissingOptionalDependencyException
import glob
import logging


class CDX_Combine:

    def __init__(self):
        self._logger = logging.getLogger('cdxc')
        self._new_bom_components = dict()
        self._new_bom_ref_map = dict()

    def _clone_component(self, bom_ref_str: str, component: Component) -> Component:
        return Component(
            bom_ref=bom_ref_str,
            type=component.type,
            group=component.group,
            name=component.name,
            version=component.version,
            author=component.author,
            copyright=component.copyright,
            description=component.description,
            licenses=component.licenses,
            supplier=component.supplier,
            purl=component.purl,
            cpe=component.cpe,
            evidence=component.evidence,
            external_references=component.external_references,
            hashes=component.hashes,
            mime_type=component.mime_type,
            pedigree=component.pedigree,
            properties=component.properties,
            release_notes=component.release_notes,
            scope=component.scope,
            swid=component.swid)
    
    def _get_ref_from_component(self, component: Component) -> str:
        if component.group:
            return f'cdxc:{component.group}/{component.name}@{component.version}'
        return f'cdxc:{component.name}@{component.version}'
    
    def _lookup_new_bom_ref(self, dependency: Dependency) -> str|None:
        if str(dependency.ref) not in self._new_bom_ref_map:
            self._logger.error(f'BOM reference {dependency.ref} unknown!')
            return None
        return self._new_bom_ref_map[str(dependency.ref)]
    
    def _lookup_component(self, dependency: Dependency) -> Component:
        new_bom_ref = self._lookup_new_bom_ref(dependency)
        if new_bom_ref not in self._new_bom_components:
            self._logger.error(f'BOM reference {new_bom_ref} not found!')
            return None
        return self._new_bom_components[new_bom_ref]

    def _simplify_ref(self, bom_ref: str|BomRef) -> str:
        bom_ref_str = old_bom_ref_str = str(bom_ref)
        if '|' in bom_ref_str:
            bom_ref_str = bom_ref_str.split('|').pop()
            self._logger.debug(f'Mapping {old_bom_ref_str} onto {bom_ref_str}')
        return bom_ref_str

    def _add_components(self, new_bom: Bom, component: Component):
        bom_ref_str = self._get_ref_from_component(component)
        bom_ref_orig_str = str(component.bom_ref)
        if bom_ref_str not in self._new_bom_components:
            self._logger.debug(f'Adding component {bom_ref_str}')
            new_component = self._clone_component(bom_ref_str, component)
            new_bom.components.add(new_component)
            self._new_bom_components[bom_ref_str] = new_component
        
        self._new_bom_ref_map[bom_ref_orig_str] = bom_ref_str
        for subcomponent in component.components:
            self._add_components(new_bom, subcomponent)

    def _mirror_dependencies(self, new_bom: Bom, dependency: Dependency):
        self._logger.debug(f'Processing dependecy {dependency.ref}')
        dependency_component = self._lookup_component(dependency)
        if dependency_component is not None:
            for subdependency in dependency.dependencies:
                subdependency_component = self._lookup_component(subdependency)
                if subdependency_component is not None:
                    new_bom.register_dependency(dependency_component, [subdependency_component])
                    self._mirror_dependencies(new_bom, subdependency)

    def run(self, args):
        name: str = args.name
        version: str = args.version
        ref = name.lower().replace(' ', '_')
        files = args.files

        self._logger.setLevel(logging.DEBUG if args.verbose else logging.INFO)
        
        self._logger.info(f'Generating SBOM for {name} {version} from {", ".join(files)}...')

        boms = []
        for file in files:
            for file in glob.glob(file):
                logging.info(f'Loading {file}...')
                with open(file, 'r') as input_file:
                    boms.append(Bom.from_json(data=json.loads(input_file.read())))

        new_bom = Bom()
        new_bom.metadata.component = root_component = Component(name=name, type=ComponentType.APPLICATION, licenses=[], bom_ref=ref, version=version)

        for bom in boms:
            bom_ref_str_orig = bom.metadata.component.bom_ref.value
            bom_ref_str = self._get_ref_from_component(bom.metadata.component)
            bom_component = self._clone_component(bom_ref_str, bom.metadata.component)
            self._logger.info(f'Processing {bom_ref_str_orig}...')

            new_bom_ref = self._get_ref_from_component(bom_component)
            bom_component.bom_ref.value = new_bom_ref

            new_bom.components.add(bom_component)
            self._new_bom_components[bom_ref_str] = bom_component
            self._new_bom_ref_map[bom_ref_str_orig] = self._get_ref_from_component(bom_component)

            for component in bom.components:
                self._add_components(new_bom, component)

            for dependency in bom.dependencies:
                self._mirror_dependencies(new_bom, dependency)

            new_bom.register_dependency(root_component, [bom_component])

        self._logger.info(f'New SBOM {args.output} contains {len(self._new_bom_components)} components')

        my_json_outputter: 'JsonOutputter' = JsonV1Dot5(new_bom)
        serialized_json = my_json_outputter.output_as_string(indent=2)

        my_json_validator = JsonStrictValidator(SchemaVersion.V1_5)
        try:
            validation_errors = my_json_validator.validate_str(serialized_json)
            if validation_errors:
                self._logger.error(f'JSON invalid:\nValidationError:\n{repr(validation_errors)}')
                #sys.exit(2)
            #print('JSON valid')
        except MissingOptionalDependencyException as error:
            self._logger.error(f'JSON-validation was skipped due to {error}')
            
        with open(args.output, 'w') as f:
            f.write(serialized_json)

