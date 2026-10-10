class DSTParser:
    """
    Parser for DST anim/build binary formats.
    """
    def __init__(self, data):
        self.data = data

    def parse_anim(self):
        # Logic to handle ANIM magic and frame offsets
        # Based on findings: 64B dynamic header + 3x 64B static blocks
        pass

    def parse_build(self):
        # Logic to handle BILD magic and transform layout
        pass
