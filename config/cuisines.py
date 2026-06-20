"""Design blueprint 2 §3: Cuisine genre list.

Serves as the key for genre-level normalization (design blueprint 1, signal 4).
"""

CUISINES = [
    "tapas",
    "japanese",
    "italian",
    "catalan",
    "seafood",
    "vegetarian",
    "burger",
    "ramen",
    "paella",
    "brunch",
]


if __name__ == "__main__":
    assert len(CUISINES) == len(set(CUISINES))
    print(f"cuisines.py OK: {len(CUISINES)} cuisines")
