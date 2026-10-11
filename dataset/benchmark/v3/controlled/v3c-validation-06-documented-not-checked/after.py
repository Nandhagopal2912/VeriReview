def make_canvas(width, height):
    """Create an empty canvas.

    :param width: number of columns; must be positive
    :param height: number of rows
    """
    return [[0] * width for _ in range(height)]
