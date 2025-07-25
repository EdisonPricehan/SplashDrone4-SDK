import os
import glob
import cv2
import numpy as np


def build_homography(img_shape, pitch_deg=15):
    h, w = img_shape[:2]
    # Intrinsic matrix approximation
    f = w  # focal length in px
    cx, cy = w / 2, h / 2
    K = np.array([[f, 0, cx],
                  [0, f, cy],
                  [0, 0,  1]], dtype=float)
    K_inv = np.linalg.inv(K)

    # Rotation about camera X‑axis (pitch), convert to radians
    theta = np.deg2rad(pitch_deg)
    Rx = np.array([[1,          0,           0],
                   [0, np.cos(theta), -np.sin(theta)],
                   [0, np.sin(theta),  np.cos(theta)]], dtype=float)

    # Homography: H = K * Rx * K⁻¹
    return K.dot(Rx).dot(K_inv)


def rectify_images(input_dir, output_dir, pitch_deg=15):
    os.makedirs(output_dir, exist_ok=True)
    img_paths = sorted(glob.glob(os.path.join(input_dir, '*.jpg')) + glob.glob(os.path.join(input_dir, '*.jpeg')))
    if not img_paths:
        print("No images found in", input_dir)
        return

    # Build homography using first image size
    sample = cv2.imread(img_paths[0])
    if sample is None:
        raise ValueError("Failed to read:", img_paths[0])
    H = build_homography(sample.shape, pitch_deg)

    for path in img_paths:
        img = cv2.imread(path)
        dst = cv2.warpPerspective(img, H, (img.shape[1], img.shape[0]), flags=cv2.INTER_LINEAR)
        fname = os.path.basename(path)
        cv2.imwrite(os.path.join(output_dir, fname), dst)
        print("Saved rectified:", fname)


if __name__ == '__main__':
    rectify_images('../images_exif', '../images_nadir', pitch_deg=15)
