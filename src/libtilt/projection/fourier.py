import torch
import torch.nn.functional as F
import einops

from libtilt.utils.coordinates import array_to_grid_sample, generate_rotated_slice_coordinates


def extract_slices(
        dft: torch.Tensor,
        slice_coordinates: torch.Tensor
) -> torch.Tensor:
    """Sample batches of 2D images from a complex cubic volume at specified coordinates.


    `dft` should pre-fftshifted to place the origin in Fourier space at the center of the DFT
    i.e. dft should be the result of

            volume -> fftshift(volume) -> fft3(volume) -> fftshift(volume)

    Coordinates should be ordered zyx, aligned with image dimensions.
    Coordinates should be array coordinates, spanning `[0, N-1]` for a dimension of length N.


    Parameters
    ----------
    dft: torch.Tensor
        (d, h, w) complex valued cubic volume (d == h == w) containing
        the discrete Fourier transform of a cubic volume.
    slice_coordinates: torch.Tensor
        (batch, h, w, zyx) array of coordinates at which `dft` should be sampled.

    Returns
    -------
    samples: torch.Tensor
        (batch, h, w) array of complex valued images sampled from the `dft`
    """
    # cannot sample complex tensors directly with grid_sample
    # c.f. https://github.com/pytorch/pytorch/issues/67634
    # workaround: treat real and imaginary parts as separate channels
    dft = einops.rearrange(torch.view_as_real(dft), 'd h w complex -> complex d h w')
    n_slices = slice_coordinates.shape[0]
    dft = einops.repeat(dft, 'complex d h w -> b complex d h w', b=n_slices)
    slice_coordinates = array_to_grid_sample(slice_coordinates, array_shape=dft.shape[-3:])

    # add a length 1 depth dim required for use with F.grid_sample
    slice_coordinates = einops.rearrange(slice_coordinates, 'b h w xyz -> b 1 h w xyz')
    samples = F.grid_sample(
        input=dft,
        grid=slice_coordinates,
        mode='bilinear',  # this is trilinear when input is volumetric
        padding_mode='zeros',
        align_corners=True,
    )
    samples = einops.rearrange(samples, 'b complex 1 h w -> b h w complex')
    samples = torch.view_as_complex(samples.contiguous())
    return samples  # (b, h, w)


def project(volume: torch.Tensor, rotation_matrices: torch.Tensor, pad=True) -> torch.Tensor:
    """Fourier space projection by sampling central slices."""
    if pad is True:
        pad_length = volume.shape[-1] // 2
        volume = F.pad(volume, pad=[pad_length]*6, mode='constant', value=None)
    dft = torch.fft.fftshift(volume, dim=(-3, -2, -1))
    dft = torch.fft.fftn(dft, dim=(-3, -2, -1))
    dft = torch.fft.fftshift(dft, dim=(-3, -2, -1))
    slice_coordinates = generate_rotated_slice_coordinates(rotation_matrices, sidelength=dft.shape[-1])
    projections = extract_slices(dft, slice_coordinates)  # (b, h, w)
    projections = torch.fft.ifftshift(projections, dim=(-2, -1))
    projections = torch.fft.ifftn(projections, dim=(-2, -1))
    projections = torch.fft.ifftshift(projections, dim=(-2, -1))
    if pad is True:
        projections = projections[:, pad_length:-pad_length, pad_length:-pad_length]
    return torch.real(projections)
