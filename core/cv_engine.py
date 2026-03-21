import cv2
import numpy as np
import trimesh
from shapely.geometry import Polygon

def process_image_to_3d(image_path: str, output_glb_path: str, wall_height: float = 30.0):
    # Load image in grayscale (supports Unicode / Korean paths on Windows)
    img_array = np.fromfile(image_path, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError(f"Could not read image file {image_path}")
    
    # 1. Binarization (Assume white background, black lines)
    # Threshold: anything darker than 200 becomes white (255), rest becomes black (0)
    # This isolates the dark wall lines.
    _, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 2. Morphological Closing to connect broken lines
    kernel = np.ones((5, 5), np.uint8)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    
    # Dilate to make walls thicker
    kernel_dilate = np.ones((3, 3), np.uint8)
    thresh = cv2.dilate(thresh, kernel_dilate, iterations=1)
    
    # 3. Find Contours
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    meshes = []
    
    # Get image dimension for scaling
    h, w = img.shape
    scale_factor = 0.1  # Arbitrary scale so the mesh isn't 1000s of units wide
    
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 50:  # Ignore tiny artifacts
            continue
            
        # Simplify contour
        epsilon = 0.005 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)
        
        if len(approx) < 3:
            continue
            
        # Scale coordinates and center to roughly (0,0)
        points = []
        for pt in approx:
            x, y = pt[0]
            # Center and scale
            px = (x - w/2) * scale_factor
            py = (y - h/2) * scale_factor
            points.append((px, -py)) # Invert Y so up is up
            
        try:
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
                
            if poly.geom_type == 'MultiPolygon':
                polys = list(poly.geoms)
            else:
                polys = [poly]
                
            for p in polys:
                if p.area < 1:
                    continue
                # 4. Extrude the polygon into a 3D Mesh
                mesh = trimesh.creation.extrude_polygon(p, height=wall_height)
                # Trimesh extrusion lays on XY plane and grows to Z. 
                # Three.js usually expects Y up. Rotate -90 on X-axis.
                # Transform matrix:
                rm = trimesh.transformations.rotation_matrix(-np.pi/2, [1, 0, 0])
                mesh.apply_transform(rm)
                meshes.append(mesh)
                
        except Exception as e:
            print(f"Error processing contour: {e}")
            continue
            
    # Combine all individual wall meshes
    if meshes:
        scene = trimesh.Scene(meshes)
        scene.export(output_glb_path)
    else:
        raise ValueError("도면에서 벽체를 인식하지 못했습니다. 너무 흐리거나 복잡한 도면일 수 있습니다.")
