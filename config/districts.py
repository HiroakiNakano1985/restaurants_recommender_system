"""Design blueprint 2 §3: Barcelona district list (tagged tourist/local).

`tourist`:
    True  ... Tourist district (ratings tend to inflate due to terraces/ambiance)
    False ... Local district
    None  ... Mixed
In the synthetic data (§4), this tag is used as the district's tourist probability.
"""

DISTRICTS = [
    # --- Tourist districts (includes the examples from design blueprint 2) ---
    {"name": "La Rambla", "tourist": True},
    {"name": "Barceloneta", "tourist": True},
    {"name": "Gothic Quarter", "tourist": True},
    {"name": "El Born", "tourist": True},
    {"name": "Port Vell", "tourist": True},
    {"name": "Sagrada Família", "tourist": True},
    {"name": "Montjuïc", "tourist": True},
    # --- Local districts (includes the examples from design blueprint 2) ---
    {"name": "Gràcia", "tourist": False},
    {"name": "Sant Andreu", "tourist": False},
    {"name": "Sants", "tourist": False},
    {"name": "Horta", "tourist": False},
    {"name": "Nou Barris", "tourist": False},
    {"name": "Poblenou", "tourist": False},
    {"name": "Poble-sec", "tourist": False},
    {"name": "Sant Gervasi", "tourist": False},
    {"name": "Sarrià", "tourist": False},
    # --- Mixed ---
    {"name": "Eixample", "tourist": None},
    {"name": "Sant Martí", "tourist": None},
    {"name": "Les Corts", "tourist": None},
    {"name": "El Raval", "tourist": None},
]


if __name__ == "__main__":
    assert all({"name", "tourist"} <= set(d) for d in DISTRICTS)
    print(f"districts.py OK: {len(DISTRICTS)} districts")
