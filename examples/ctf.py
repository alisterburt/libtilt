import napari
import torch

from libtilt.ctf import calculate_ctf

ctf_images = calculate_ctf(
    defocus=1,
    astigmatism=0,
    astigmatism_angle=0,
    voltage=300,
    spherical_aberration=2.7,
    amplitude_contrast=0.1,
    b_factor=0,
    phase_shift=0,
    pixel_size=torch.linspace(10, 0.5, steps=50),
    image_shape=(512, 512),
    rfft=False,
    fftshift=True
)

viewer = napari.Viewer()
viewer.add_image(ctf_images.numpy())
napari.run()