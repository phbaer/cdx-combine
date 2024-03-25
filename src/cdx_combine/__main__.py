from cdx_combine import CDX_Combine
import argparse
import logging

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
                    prog='cdx_combine',
                    description='Combines multiple CycloneDX SBOM files into one. It will keep the component names.')
    parser.add_argument('files', nargs='*')
    parser.add_argument('-o', '--output', default='cyclonedx.json')
    parser.add_argument('-n', '--name', required=True)
    parser.add_argument('-v', '--version', required=True)
    parser.add_argument(      '--verbose', action="store_true")

    
    try:
        args = parser.parse_args()

        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
        logger = logging.getLogger('main')
        
        if 'files' not in args or args.files is None or len(args.files) == 0:
            logger.error(f'At least one input file required!')
            exit(1)
            
        CDX_Combine().run(args)
    except SystemExit as e:
        pass
