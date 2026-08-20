import matplotlib.pyplot as plt
import numpy as np

gradient = np.linspace(0, 1, 512).reshape(1, -1)
gradient = np.vstack((gradient, gradient))

dpi = 300
width_px = 2400
height_px = 80
figsize = (width_px / dpi, height_px / dpi)

colormaps = ['viridis', 'plasma', 'inferno', 'magma']
for cmap in colormaps:
    plt.figure(figsize=figsize)
    plt.imshow(gradient, aspect='auto', cmap=cmap)
    plt.axis('off')
    plt.savefig(f'./../Assets/Resources/Colormaps/{cmap}.png', bbox_inches='tight', pad_inches=0)