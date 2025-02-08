class Player:
    def __init__(self, name: str, stone: int, is_ai: bool):
        """

        Args:
            name (str): player's name
            stone (int): represent the player's stone
            is_ai (bool): whether the player is AI or not
        """
        self.name = name
        self.stone = stone
        self.is_ai = is_ai
