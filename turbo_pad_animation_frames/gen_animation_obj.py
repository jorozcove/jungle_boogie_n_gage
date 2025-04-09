#!/usr/bin/env python3
import os
import math
from PIL import Image, ImageChops

# PARAMETERS
N_FRAMES = 15           # number of scrolling frames to generate (plus one duplicate for perfect loop)
SUBDIVISIONS = 2       # number of subdivisions per side for each square mesh
SCROLL_DIRECTION = 'horizontal'  # supports 'horizontal' or 'vertical'
MERGE_TOL = 0.0001      # merging tolerance in meters

# Filenames for OBJ and MTL files
OBJ_FILENAME = "animation.obj"
MTL_FILENAME = "animation.mtl"

def generate_scrolled_frames(image_path, n_frames, direction='horizontal'):
    """
    Reads an image and generates n_frames+1 frames by scrolling the image.
    The last frame is exactly the same as the first, ensuring a perfect loop.
    Saves each frame as frame_0.png, frame_1.png, ..., frame_n_frames.png.
    (You can ignore the last duplicate frame when playing the animation.)
    """
    img = Image.open(image_path)
    width, height = img.size
    frames = []
    # Use n_frames as the number of steps; generate n_frames+1 frames so that frame_n is identical to frame_0.
    for i in range(n_frames + 1):
        if direction == 'horizontal':
            # Compute a fractional shift such that the last frame is exactly the same as the first.
            shift_x = int(round(i * width / n_frames)) % width
            shifted = ImageChops.offset(img, shift_x, 0)
        elif direction == 'vertical':
            shift_y = int(round(i * height / n_frames)) % height
            shifted = ImageChops.offset(img, 0, shift_y)
        else:
            raise ValueError("Unsupported scroll direction")
        
        frame_filename = f"frame_{i}.png"
        shifted.save(frame_filename)
        frames.append(frame_filename)
        print(f"Saved {frame_filename} with shift {shift_x if direction=='horizontal' else shift_y}")
    return frames

def create_subdivided_square(subdivisions):
    """
    Creates a subdivided square mesh.
    The square spans (0,0,0) to (1,1,0) with texture coordinates matching the vertex positions.
    Returns a tuple (vertices, texcoords, faces) where:
      - vertices: list of (x, y, z)
      - texcoords: list of (u, v)
      - faces: list of faces, where each face is a tuple of 4 vertex indices (OBJ indices start at 1)
    """
    vertices = []
    texcoords = []
    faces = []
    
    # Generate vertices and texture coordinates.
    for j in range(subdivisions + 1):
        for i in range(subdivisions + 1):
            x = i / subdivisions
            y = j / subdivisions
            vertices.append((x, y, 0))
            texcoords.append((x, y))
    
    # Generate faces (each quad face uses 4 vertices)
    for j in range(subdivisions):
        for i in range(subdivisions):
            idx_bl = j * (subdivisions + 1) + i + 1
            idx_br = idx_bl + 1
            idx_tl = (j + 1) * (subdivisions + 1) + i + 1
            idx_tr = idx_tl + 1
            faces.append((idx_bl, idx_br, idx_tr, idx_tl))
    
    return vertices, texcoords, faces

def merge_vertices(vertices, texcoords, faces, tol=MERGE_TOL):
    """
    Merges vertices (and their associated texture coordinates) that are within tol distance.
    Returns new lists: merged_vertices, merged_texcoords, and new_faces with updated indices.
    """
    merged = []         # list of (vertex, texcoord)
    mapping = {}        # original index -> new index
    for i, (v, uv) in enumerate(zip(vertices, texcoords)):
        found = False
        for new_idx, (mv, muv) in enumerate(merged):
            # Compute Euclidean distance between vertices
            if math.dist(v, mv) < tol and math.dist(uv, muv) < tol:
                mapping[i] = new_idx
                found = True
                break
        if not found:
            mapping[i] = len(merged)
            merged.append((v, uv))
    
    merged_vertices = [v for v, _ in merged]
    merged_texcoords = [uv for _, uv in merged]
    
    # Update face indices using the mapping; note that OBJ indices start at 1 so adjust accordingly later.
    new_faces = []
    for face in faces:
        new_face = tuple(mapping[idx - 1] + 1 for idx in face)
        new_faces.append(new_face)
    
    return merged_vertices, merged_texcoords, new_faces

def write_obj_and_mtl(frames, subdivisions, obj_filename, mtl_filename):
    """
    Writes an OBJ file containing one mesh per frame.
    Each mesh is a subdivided square (with vertices, texture coordinates, and faces)
    that is merged by distance and is assigned a material that references the corresponding frame image.
    All meshes are overlapped at 0,0,0.
    """
    # Create the subdivided square data.
    base_vertices, base_texcoords, base_faces = create_subdivided_square(subdivisions)
    # Merge vertices that are within MERGE_TOL
    merged_vertices, merged_texcoords, merged_faces = merge_vertices(base_vertices, base_texcoords, base_faces, MERGE_TOL)
    
    with open(obj_filename, "w") as obj_file, open(mtl_filename, "w") as mtl_file:
        # Write reference to the material file.
        obj_file.write(f"mtllib {mtl_filename}\n")
        
        vertex_offset = 0  # tracks the number of vertices written so far
        # Loop over each frame (each mesh)
        for i, frame_img in enumerate(frames):
            obj_file.write(f"\no Mesh_{i}\n")
            obj_file.write(f"usemtl mat_{i}\n")
            
            # Write vertices for this mesh.
            for v in merged_vertices:
                obj_file.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            
            # Write texture coordinates.
            for vt in merged_texcoords:
                obj_file.write(f"vt {vt[0]:.6f} {vt[1]:.6f}\n")
            
            # Write faces. Adjust indices by vertex_offset.
            for face in merged_faces:
                v1, v2, v3, v4 = [idx + vertex_offset for idx in face]
                obj_file.write(f"f {v1}/{v1} {v2}/{v2} {v3}/{v3} {v4}/{v4}\n")
            
            # Increase offset by the number of vertices in this mesh.
            vertex_offset += len(merged_vertices)
            
            # Write material for this mesh to the MTL file.
            mtl_file.write(f"newmtl mat_{i}\n")
            mtl_file.write("Ka 1.000 1.000 1.000\n")
            mtl_file.write("Kd 1.000 1.000 1.000\n")
            mtl_file.write(f"map_Kd {frame_img}\n\n")
            
            print(f"Mesh for {frame_img} written with {len(merged_vertices)} vertices and {len(merged_faces)} faces.")

def main():
    # Check if the starting image exists.
    if not os.path.exists("frame_0.png"):
        print("Error: 'frame_0.png' not found in the current directory.")
        return
    
    # Step 1: Generate scrolled frames (note: the last frame is a duplicate of the first).
    frames = generate_scrolled_frames("frame_0.png", N_FRAMES-1, SCROLL_DIRECTION)
    
    # Step 2: Create OBJ and MTL files with merged subdivided square meshes (one per frame).
    write_obj_and_mtl(frames, SUBDIVISIONS, OBJ_FILENAME, MTL_FILENAME)
    
    print(f"\nOBJ file '{OBJ_FILENAME}' and MTL file '{MTL_FILENAME}' have been created.")

if __name__ == "__main__":
    main()
