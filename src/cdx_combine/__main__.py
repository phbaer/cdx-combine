from cdx_combine import CDX_Combine
import argparse
import logging

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
                    prog='cdx_combine',
                    description='Combines multiple CycloneDX SBOM files into one. It will keep the component names.')
    parser.add_argument('files', nargs='*')
    parser.add_argument('-n', '--name', required=True)
    parser.add_argument('-v', '--version', required=True)
    
    try:
        args = parser.parse_args()
        
        if 'files' not in args or args.files is None or len(args.files) == 0:
            logging.error(f'At least one input file required!')
            exit(1)
            
        CDX_Combine().run(args)
    except SystemExit as e:
        pass
