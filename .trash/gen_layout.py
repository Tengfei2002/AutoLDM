import gdspy
import numpy as np
import argparse
from pathlib import Path

def extract_gds_bboxes(gds_path, output_path):
    # Check if the input file exists
    if not Path(gds_path).exists():
        print(f"Error: Input file {gds_path} not found")
        return

    # Ensure the output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    print(f"Reading {gds_path} ...")
    
    # Load GDS library and get top-level cells
    lib = gdspy.GdsLibrary(infile=gds_path)
    top_cells = lib.top_level()
    
    if not top_cells:
        print("Warning: No top-level cells found in the GDS file.")
        return

    # Extract polygons and write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        for cell in top_cells:
            poly_dict = cell.get_polygons(by_spec=True)
            for (layer, datatype), polygons in poly_dict.items():
                for points in polygons:
                    x_min, y_min = np.min(points, axis=0)
                    x_max, y_max = np.max(points, axis=0)
                    f.write(f"{x_min:.4f} {y_min:.4f} {x_max:.4f} {y_max:.4f} {layer}\n")

    print(f"Extraction completed! Data saved to {output_path}")

if __name__ == '__main__':
    # 1. Instantiate argument parser
    parser = argparse.ArgumentParser(description="Extract bounding boxes of polygons from GDS file")
    
    # 2. Add positional arguments (required)
    parser.add_argument("input_gds", type=str, help="Path to input GDS file (e.g. ./gds/test.gds)")
    
    # 3. Parse command line arguments
    args = parser.parse_args()
    
    # 4. Dynamic path processing
    input_path = Path(args.input_gds)
    
    # input_path.stem gets filename without extension (e.g. test.gds -> test)
    output_filename = f"{input_path.stem}_gds.txt"
    
    # input_path.parent gets the directory of the file, safely concatenate path
    output_path = input_path.parent / output_filename
    
    # 5. Run extraction logic (convert Path object to string)
    extract_gds_bboxes(str(input_path), str(output_path))